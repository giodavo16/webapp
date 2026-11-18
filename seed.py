"""Popolamento demo: account di prova, catalogo, tag e qualche voto."""

import DB_tool
import sicurezza

UTENTI = [
    ("Elena Ruggeri", "gestore@auroratecnologie.it", "Gestore!2026", "gestore"),
    ("Mario Rossi", "mario.rossi@example.it", "Base!2026", "base"),
    ("Giulia Pavesi", "giulia.pavesi@example.it", "Base!2026", "base"),
]

CATEGORIE = [
    ("Informatica", "Postazioni, monitor e componenti"),
    ("Accessori", "Periferiche e complementi"),
    ("Audio", "Cuffie e diffusori"),
    ("Rete", "Switch, firewall e cablaggio"),
]

TAG = ["aziendale", "economico", "premium", "portatile", "silenzioso", "ufficio"]

PRODOTTI = [
    ("Laptop", "Notebook 14\" aziendale, 16 GB RAM", 899.99, "Informatica", ["aziendale", "premium"]),
    ("Mouse wireless", "Ricevitore USB, silenzioso", 24.99, "Accessori", ["economico", "silenzioso"]),
    ("Tastiera meccanica", "Switch lineari, layout IT", 79.90, "Accessori", ["ufficio"]),
    ("Monitor 27 pollici", "IPS QHD, hub USB-C", 249.99, "Informatica", ["ufficio", "premium"]),
    ("Cuffie Bluetooth", "Cancellazione attiva del rumore", 59.90, "Audio", ["portatile"]),
    ("Webcam HD", "1080p con microfono", 39.99, "Accessori", ["ufficio"]),
    ("Speaker Bluetooth", "10 W, autonomia 12 h", 45.00, "Audio", ["portatile", "economico"]),
    ("Switch 24 porte", "Managed, VLAN e PoE", 189.00, "Rete", ["aziendale"]),
]


def main():
    conn = DB_tool.connetti()
    if conn is None:
        raise SystemExit("Connessione al database non riuscita: controlla il file .env")
    with conn.cursor() as cursore:
        for tabella in ("audit_log", "voti", "prodotto_tag", "compilazioni",
                        "prodotti", "categorie", "tag", "profili", "immagini", "utenti"):
            cursore.execute(f"DELETE FROM {tabella}")
    conn.commit()
    conn.close()

    for nome, email, password, ruolo in UTENTI:
        utente_id = DB_tool.crea_utente(
            nome, email, sicurezza.genera_hash(password), sicurezza.sha256("seed")
        )
        conn = DB_tool.connetti()
        with conn.cursor() as cursore:
            cursore.execute(
                "UPDATE utenti SET is_verified = 1, ruolo = %s WHERE id = %s",
                (ruolo, utente_id),
            )
        conn.commit()
        conn.close()

    for nome, descrizione in CATEGORIE:
        conn = DB_tool.connetti()
        with conn.cursor() as cursore:
            cursore.execute(
                "INSERT INTO categorie (nome, descrizione) VALUES (%s, %s)",
                (nome, descrizione),
            )
        conn.commit()
        conn.close()

    for nome in TAG:
        conn = DB_tool.connetti()
        with conn.cursor() as cursore:
            cursore.execute("INSERT INTO tag (nome) VALUES (%s)", (nome,))
        conn.commit()
        conn.close()

    mappa = {c["nome"]: c["id"] for c in DB_tool.elenco_categorie()}
    for nome, descrizione, prezzo, categoria, tag in PRODOTTI:
        prodotto_id = DB_tool.crea_prodotto(
            nome, descrizione, prezzo, mappa[categoria], None, 1
        )
        DB_tool.salva_tag_prodotto(prodotto_id, tag)

    DB_tool.salva_voto(2, 1, 4, "Buona dotazione, un po' caro.")
    DB_tool.salva_voto(3, 2, 5, "Silenzioso davvero.")
    DB_tool.log(1, "seed", "sistema", None, "Popolamento demo completato")

    print(f"Inseriti {len(UTENTI)} utenti, {len(CATEGORIE)} categorie, "
          f"{len(PRODOTTI)} prodotti, {len(TAG)} tag.")
    print("Gestore: gestore@auroratecnologie.it / Gestore!2026")
    print("Base:    mario.rossi@example.it / Base!2026")


if __name__ == "__main__":
    main()