"""Unico punto di accesso al database. Ogni query è parametrizzata."""

import os

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor

load_dotenv()


def connetti():
    try:
        return pymysql.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )
    except pymysql.Error as errore:
        print("Connessione al database non riuscita:", errore)
        return None


def _query(sql, parametri=(), tipo="tutti"):
    """tipo: tutti | uno | id | conta."""
    conn = connetti()
    if conn is None:
        return [] if tipo == "tutti" else (None if tipo == "uno" else 0)
    try:
        with conn.cursor() as cursore:
            cursore.execute(sql, parametri)
            if tipo == "tutti":
                return cursore.fetchall()
            if tipo == "uno":
                return cursore.fetchone()
            if tipo == "id":
                conn.commit()
                return cursore.lastrowid
            conn.commit()
            return cursore.rowcount
    except pymysql.Error as errore:
        conn.rollback()
        print("Errore SQL:", errore)
        return [] if tipo == "tutti" else (None if tipo == "uno" else 0)
    finally:
        conn.close()


# ---------------- UTENTI ----------------

def utente_per_email(email):
    return _query(
        """SELECT id, nome, email, password_hash, ruolo, is_verified, bloccato_fino
           FROM utenti WHERE email = %s""",
        (email,), "uno",
    )


def utente_per_id(utente_id):
    return _query(
        """SELECT u.id, u.nome, u.email, u.ruolo, u.is_verified, u.creato_il,
                  p.telefono, p.citta, p.bio, p.avatar_id
           FROM utenti u LEFT JOIN profili p ON p.utente_id = u.id
           WHERE u.id = %s""",
        (utente_id,), "uno",
    )


def crea_utente(nome, email, password_hash, token_verifica):
    return _query(
        """INSERT INTO utenti (nome, email, password_hash, token_verifica)
           VALUES (%s, %s, %s, %s)""",
        (nome, email, password_hash, token_verifica), "id",
    )


def verifica_utente(token_hash):
    righe = _query(
        """UPDATE utenti SET is_verified = 1, token_verifica = NULL
           WHERE token_verifica = %s AND is_verified = 0""",
        (token_hash,), "conta",
    )
    return righe > 0


def registra_accesso(utente_id, fallito=False):
    if fallito:
        _query(
            """UPDATE utenti
               SET tentativi_falliti = tentativi_falliti + 1,
                   bloccato_fino = CASE WHEN tentativi_falliti + 1 >= 5
                                        THEN NOW() + INTERVAL 10 MINUTE
                                        ELSE bloccato_fino END
               WHERE id = %s""",
            (utente_id,), "conta",
        )
        return
    _query(
        """UPDATE utenti SET tentativi_falliti = 0, bloccato_fino = NULL,
                             ultimo_accesso = NOW()
           WHERE id = %s""",
        (utente_id,), "conta",
    )


def elenco_utenti():
    return _query(
        """SELECT u.id, u.nome, u.email, u.ruolo, u.is_verified, u.creato_il,
                  COUNT(v.id) AS voti
           FROM utenti u LEFT JOIN voti v ON v.utente_id = u.id
           GROUP BY u.id ORDER BY u.ruolo, u.nome"""
    )


def cambia_ruolo(utente_id, ruolo):
    return _query("UPDATE utenti SET ruolo = %s WHERE id = %s",
                  (ruolo, utente_id), "conta")


def elimina_utente(utente_id):
    return _query("DELETE FROM utenti WHERE id = %s", (utente_id,), "conta")


def conta_gestori():
    riga = _query("SELECT COUNT(*) AS n FROM utenti WHERE ruolo = 'gestore'", (), "uno")
    return riga["n"] if riga else 0


# ---------------- PROFILI ----------------

def salva_profilo(utente_id, telefono, citta, bio, avatar_id):
    return _query(
        """INSERT INTO profili (utente_id, telefono, citta, bio, avatar_id)
           VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE telefono = VALUES(telefono),
             citta = VALUES(citta), bio = VALUES(bio),
             avatar_id = COALESCE(VALUES(avatar_id), avatar_id)""",
        (utente_id, telefono, citta, bio, avatar_id), "conta",
    )


# ---------------- IMMAGINI ----------------

def salva_immagine(nome_file, mime, dati, utente_id):
    return _query(
        """INSERT INTO immagini (nome_file, mime, dati, caricata_da)
           VALUES (%s, %s, %s, %s)""",
        (nome_file[:160], mime, dati, utente_id), "id",
    )


def immagine_per_id(immagine_id):
    return _query("SELECT nome_file, mime, dati FROM immagini WHERE id = %s",
                  (immagine_id,), "uno")


def elimina_immagine(immagine_id):
    return _query("DELETE FROM immagini WHERE id = %s", (immagine_id,), "conta")


# ---------------- CATEGORIE E TAG ----------------

def elenco_categorie():
    return _query("SELECT id, nome, descrizione FROM categorie ORDER BY nome")


def elenco_tag():
    return _query("SELECT id, nome FROM tag ORDER BY nome")


def tag_prodotto(prodotto_id):
    return _query(
        """SELECT t.id, t.nome FROM tag t
           JOIN prodotto_tag pt ON pt.tag_id = t.id
           WHERE pt.prodotto_id = %s ORDER BY t.nome""",
        (prodotto_id,),
    )


def salva_tag_prodotto(prodotto_id, nomi_tag):
    """N:M: azzera e riscrive, creando i tag che non esistono."""
    _query("DELETE FROM prodotto_tag WHERE prodotto_id = %s", (prodotto_id,), "conta")
    for nome in nomi_tag:
        nome = nome.strip().lower()[:40]
        if not nome:
            continue
        _query("INSERT INTO tag (nome) VALUES (%s) ON DUPLICATE KEY UPDATE id = id",
               (nome,), "conta")
        _query(
            """INSERT INTO prodotto_tag (prodotto_id, tag_id)
               SELECT %s, id FROM tag WHERE nome = %s""",
            (prodotto_id, nome), "conta",
        )


# ---------------- PRODOTTI ----------------

_COLONNE_PRODOTTO = """p.id, p.nome, p.descrizione, p.prezzo, p.immagine_id,
                       c.nome AS categoria, ROUND(AVG(v.stelle), 1) AS media,
                       COUNT(v.id) AS voti"""


def visualizza_prodotti(ricerca=None, categoria_id=None):
    sql = (f"SELECT {_COLONNE_PRODOTTO} FROM prodotti p "
           "JOIN categorie c ON c.id = p.categoria_id "
           "LEFT JOIN voti v ON v.prodotto_id = p.id")
    condizioni, parametri = [], []
    if ricerca:
        condizioni.append("(p.nome LIKE %s OR p.descrizione LIKE %s OR c.nome LIKE %s)")
        like = f"%{ricerca}%"
        parametri += [like, like, like]
    if categoria_id:
        condizioni.append("p.categoria_id = %s")
        parametri.append(categoria_id)
    if condizioni:
        sql += " WHERE " + " AND ".join(condizioni)
    sql += " GROUP BY p.id ORDER BY p.nome"
    return _query(sql, parametri)


def prodotto_per_id(prodotto_id):
    return _query(
        f"""SELECT {_COLONNE_PRODOTTO}, u.nome AS autore
            FROM prodotti p
            JOIN categorie c ON c.id = p.categoria_id
            LEFT JOIN voti v ON v.prodotto_id = p.id
            LEFT JOIN utenti u ON u.id = p.creato_da
            WHERE p.id = %s GROUP BY p.id""",
        (prodotto_id,), "uno",
    )


def crea_prodotto(nome, descrizione, prezzo, categoria_id, immagine_id, utente_id):
    return _query(
        """INSERT INTO prodotti (nome, descrizione, prezzo, categoria_id,
                                 immagine_id, creato_da)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (nome, descrizione, prezzo, categoria_id, immagine_id, utente_id), "id",
    )


def aggiorna_prodotto(prodotto_id, nome, descrizione, prezzo, categoria_id, immagine_id):
    return _query(
        """UPDATE prodotti SET nome = %s, descrizione = %s, prezzo = %s,
                               categoria_id = %s,
                               immagine_id = COALESCE(%s, immagine_id)
           WHERE id = %s""",
        (nome, descrizione, prezzo, categoria_id, immagine_id, prodotto_id), "conta",
    )


def elimina_prodotto(prodotto_id):
    return _query("DELETE FROM prodotti WHERE id = %s", (prodotto_id,), "conta")


# ---------------- VOTI ----------------

def voti_prodotto(prodotto_id):
    return _query(
        """SELECT v.stelle, v.commento, v.creato_il, u.nome
           FROM voti v JOIN utenti u ON u.id = v.utente_id
           WHERE v.prodotto_id = %s ORDER BY v.creato_il DESC""",
        (prodotto_id,),
    )


def voto_utente(utente_id, prodotto_id):
    return _query("SELECT stelle, commento FROM voti WHERE utente_id = %s "
                  "AND prodotto_id = %s", (utente_id, prodotto_id), "uno")


def salva_voto(utente_id, prodotto_id, stelle, commento):
    return _query(
        """INSERT INTO voti (utente_id, prodotto_id, stelle, commento)
           VALUES (%s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE stelle = VALUES(stelle),
             commento = VALUES(commento)""",
        (utente_id, prodotto_id, stelle, commento[:400]), "conta",
    )


def elimina_voto(utente_id, prodotto_id):
    return _query("DELETE FROM voti WHERE utente_id = %s AND prodotto_id = %s",
                  (utente_id, prodotto_id), "conta")


# ---------------- AMMINISTRAZIONE ----------------

def statistiche():
    riga = _query(
        """SELECT (SELECT COUNT(*) FROM prodotti) AS prodotti,
                  (SELECT COUNT(*) FROM categorie) AS categorie,
                  (SELECT COUNT(*) FROM utenti) AS utenti,
                  (SELECT COUNT(*) FROM voti) AS voti,
                  (SELECT COUNT(*) FROM immagini) AS immagini""",
        (), "uno",
    )
    return riga or {"prodotti": 0, "categorie": 0, "utenti": 0,
                    "voti": 0, "immagini": 0}


def log(utente_id, azione, entita, entita_id, dettaglio=""):
    return _query(
        """INSERT INTO audit_log (utente_id, azione, entita, entita_id, dettaglio)
           VALUES (%s, %s, %s, %s, %s)""",
        (utente_id, azione[:40], entita[:40], entita_id, str(dettaglio)[:255]), "conta",
    )


def ultimi_log(limite=25):
    return _query(
        """SELECT l.creato_il, l.azione, l.entita, l.entita_id, l.dettaglio, u.nome
           FROM audit_log l LEFT JOIN utenti u ON u.id = l.utente_id
           ORDER BY l.id DESC LIMIT %s""",
        (int(limite),),
    )