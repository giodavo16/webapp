import hmac
import io
import os
import secrets
import time
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, jsonify, redirect, render_template, request,
    send_file, url_for,
)

import DB_tool
import email_tool
import sicurezza
from dati import INFO_AZIENDA, SEZIONI_AZIENDA, dati_profilo

load_dotenv()

app = Flask(__name__)
# MODIFICA 1: niente fallback silenzioso, la chiave deve stare nel .env
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
if not os.getenv("SECRET_KEY"):
    print("ATTENZIONE: SECRET_KEY assente nel .env, uso un valore casuale "
          "(i token di sessione decadranno a ogni riavvio).")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
DURATA_TOKEN = 60 * 30
token_attivi = {}

MIME_IMMAGINI = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "image/gif": b"GIF8",
    "image/webp": b"RIFF",
}


# ---------------- CONTESTO TEMPLATE ----------------

@app.context_processor
def inietta_contesto():
    token = token_corrente()
    sessione = leggi_token(token)
    return {
        "azienda": INFO_AZIENDA,
        "sezioni": SEZIONI_AZIENDA,
        "csrf_token": sessione["csrf"] if sessione else "",
        "token": token,
        "username": sessione["nome"] if sessione else None,
        "ruolo": sessione["ruolo"] if sessione else None,
        "e_gestore": bool(sessione and sessione["ruolo"] == "gestore"),
        **dati_profilo(),
    }


# ---------------- AUTENTICAZIONE ----------------

def token_corrente():
    return (
        request.args.get("token")
        or request.form.get("token")
        or request.cookies.get("token")
    )


def genera_token(utente):
    token = secrets.token_urlsafe(32)
    token_attivi[token] = {
        "utente_id": utente["id"],
        "nome": utente["nome"],
        "ruolo": utente["ruolo"],
        "csrf": secrets.token_urlsafe(24),
        "scadenza": time.time() + DURATA_TOKEN,
    }
    return token


def leggi_token(token):
    dati = token_attivi.get(token) if token else None
    if dati is None:
        return None
    if dati["scadenza"] < time.time():
        token_attivi.pop(token, None)
        return None
    return dati


def sessione_valida():
    return leggi_token(token_corrente())


def token_richiesto(funzione):
    @wraps(funzione)
    def wrapper(*args, **kwargs):
        if sessione_valida() is None:
            flash("Sessione scaduta o assente: effettua l'accesso.", "errore")
            return redirect(url_for("login"))
        return funzione(*args, **kwargs)

    return wrapper


def gestore_richiesto(funzione):
    """Secondo livello: oltre al token serve il ruolo gestore."""
    @wraps(funzione)
    def wrapper(*args, **kwargs):
        sessione = sessione_valida()
        if sessione is None:
            flash("Sessione scaduta o assente: effettua l'accesso.", "errore")
            return redirect(url_for("login"))
        if sessione["ruolo"] != "gestore":
            abort(403)
        return funzione(*args, **kwargs)

    return wrapper


def csrf_richiesto(funzione):
    """MODIFICA 2: i metodi senza corpo non hanno un form da cui leggere il token."""
    @wraps(funzione)
    def wrapper(*args, **kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return funzione(*args, **kwargs)
        sessione = sessione_valida()
        inviato = request.form.get("csrf") or request.headers.get("X-CSRF", "")
        if sessione and not hmac.compare_digest(inviato, sessione["csrf"]):
            abort(400, "Token CSRF mancante o non valido.")
        return funzione(*args, **kwargs)

    return wrapper


# ---------------- PAGINE PUBBLICHE ----------------

@app.route("/")
def index():
    return redirect(url_for("dashboard") if sessione_valida() else url_for("login"))


@app.route("/login")
def login():
    if sessione_valida():
        return redirect(url_for("dashboard"))
    return render_template("login.html", errore=request.args.get("errore"))


@app.route("/api/login", methods=["POST"])
def api_login():
    dati = request.get_json(silent=True) or request.form
    email = (dati.get("email") or "").strip().lower()
    password = dati.get("password") or ""

    utente = DB_tool.utente_per_email(email)
    if utente is None or not sicurezza.verifica_password(password, utente["password_hash"]):
        if utente:
            DB_tool.registra_accesso(utente["id"], fallito=True)
        return jsonify({"success": False,
                        "messaggio": "Email o password errati."}), 401

    # MODIFICA 3: NOW() del database è in fuso locale, non in UTC
    if utente["bloccato_fino"] and utente["bloccato_fino"] > datetime.now():
        return jsonify({"success": False,
                        "messaggio": "Troppi tentativi: riprova tra qualche minuto."}), 429

    if not utente["is_verified"]:
        return jsonify({"success": False,
                        "messaggio": "Account non attivo: conferma l'indirizzo email."}), 403

    DB_tool.registra_accesso(utente["id"], fallito=False)
    token = genera_token(utente)
    risposta = jsonify({"success": True, "redirect": url_for("dashboard")})
    risposta.set_cookie("token", token, httponly=True, samesite="Lax",
                        max_age=DURATA_TOKEN)
    return risposta


@app.route("/logout")
def logout():
    token = token_corrente()
    if token:
        token_attivi.pop(token, None)
    risposta = redirect(url_for("login"))
    risposta.delete_cookie("token")
    return risposta


# ---------------- REGISTRAZIONE ----------------

@app.route("/registrazione", methods=["GET", "POST"])
def registrazione():
    if request.method == "GET":
        return render_template("registrazione.html")

    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    conferma = request.form.get("conferma") or ""

    errori = []
    if len(nome) < 3:
        errori.append("Il nome deve contenere almeno 3 caratteri.")
    if "@" not in email or "." not in email.split("@")[-1]:
        errori.append("Indirizzo email non valido.")
    if len(password) < 8:
        errori.append("La password deve contenere almeno 8 caratteri.")
    if password != conferma:
        errori.append("Le due password non coincidono.")
    if DB_tool.utente_per_email(email):
        errori.append("Questa email è già registrata.")

    if errori:
        for errore in errori:
            flash(errore, "errore")
        return render_template("registrazione.html", nome=nome, email=email), 400

    token_verifica = sicurezza.genera_token_verifica()
    nuovo_id = DB_tool.crea_utente(
        nome, email, sicurezza.genera_hash(password), sicurezza.sha256(token_verifica)
    )
    if nuovo_id is None:
        flash("Registrazione non riuscita, riprova.", "errore")
        return render_template("registrazione.html", nome=nome, email=email), 500

    link = f"{BASE_URL}/conferma/{token_verifica}"
    if not email_tool.send_verification_email(email, link):
        flash("Account creato, ma la mail non è partita: controlla la configurazione SMTP.", "errore")

    DB_tool.log(nuovo_id, "registrazione", "utenti", nuovo_id, email)
    return redirect(url_for("conferma_inviata", email=email))


@app.route("/registrazione/inviata")
def conferma_inviata():
    return render_template("conferma.html", email=request.args.get("email"))


@app.route("/conferma/<token>")
def conferma_account(token):
    attivato = DB_tool.verifica_utente(sicurezza.sha256(token))
    return render_template("conferma.html", attivato=attivato)


# ---------------- PROFILO AZIENDALE ----------------

@app.route("/azienda")
@token_richiesto
def azienda():
    return render_template("azienda.html", sezioni_locali=True)


# ---------------- DASHBOARD (entrambi i ruoli) ----------------

@app.route("/dashboard")
@token_richiesto
def dashboard():
    ricerca = request.args.get("q", "").strip()
    categoria = request.args.get("categoria", type=int)
    return render_template(
        "dashboard.html",
        prodotti=DB_tool.visualizza_prodotti(ricerca or None, categoria),
        categorie=DB_tool.elenco_categorie(),
        ricerca=ricerca,
        categoria_scelta=categoria,
    )


@app.route("/prodotto/<int:prodotto_id>")
@token_richiesto
def prodotto(prodotto_id):
    scheda = DB_tool.prodotto_per_id(prodotto_id)
    if scheda is None:
        abort(404)
    sessione = sessione_valida()
    return render_template(
        "prodotto.html",
        prodotto=scheda,
        voti=DB_tool.voti_prodotto(prodotto_id),
        mio_voto=DB_tool.voto_utente(sessione["utente_id"], prodotto_id),
    )


@app.route("/prodotto/<int:prodotto_id>/vota", methods=["POST"])
@token_richiesto
@csrf_richiesto
def vota(prodotto_id):
    sessione = sessione_valida()
    stelle = request.form.get("stelle", type=int)
    commento = (request.form.get("commento") or "").strip()

    if stelle is None or not 1 <= stelle <= 5:
        flash("Seleziona un voto da 1 a 5 stelle.", "errore")
        return redirect(url_for("prodotto", prodotto_id=prodotto_id))

    DB_tool.salva_voto(sessione["utente_id"], prodotto_id, stelle, commento)
    DB_tool.log(sessione["utente_id"], "voto", "prodotti", prodotto_id, f"{stelle}/5")
    flash("Voto registrato.", "ok")
    return redirect(url_for("prodotto", prodotto_id=prodotto_id))


@app.route("/prodotto/<int:prodotto_id>/voto/elimina", methods=["POST"])
@token_richiesto
@csrf_richiesto
def elimina_voto(prodotto_id):
    sessione = sessione_valida()
    DB_tool.elimina_voto(sessione["utente_id"], prodotto_id)
    DB_tool.log(sessione["utente_id"], "elimina_voto", "prodotti", prodotto_id)
    flash("Voto rimosso.", "ok")
    return redirect(url_for("prodotto", prodotto_id=prodotto_id))


# ---------------- PROFILO PERSONALE (1:1) ----------------

@app.route("/profilo", methods=["GET", "POST"])
@token_richiesto
@csrf_richiesto
def profilo():
    sessione = sessione_valida()

    if request.method == "POST":
        immagine, errore = leggi_immagine()
        if errore:
            flash(errore, "errore")
            return redirect(url_for("profilo"))

        avatar_id = None
        if immagine:
            avatar_id = DB_tool.salva_immagine(*immagine, sessione["utente_id"])

        DB_tool.salva_profilo(
            sessione["utente_id"],
            (request.form.get("telefono") or "").strip(),
            (request.form.get("citta") or "").strip(),
            (request.form.get("bio") or "").strip(),
            avatar_id,
        )
        DB_tool.log(sessione["utente_id"], "profilo", "profili", sessione["utente_id"])
        flash("Profilo aggiornato.", "ok")
        return redirect(url_for("profilo"))

    return render_template("profilo.html", utente=DB_tool.utente_per_id(sessione["utente_id"]))


# ---------------- AREA GESTORE ----------------

@app.route("/gestione")
@gestore_richiesto
def gestione():
    return render_template(
        "gestione.html",
        prodotti=DB_tool.visualizza_prodotti(),
        utenti=DB_tool.elenco_utenti(),
        statistiche=DB_tool.statistiche(),
        log=DB_tool.ultimi_log(),
    )


@app.route("/gestione/prodotti/nuovo", methods=["GET", "POST"])
@gestore_richiesto
@csrf_richiesto
def nuovo_prodotto():
    if request.method == "GET":
        # MODIFICA 4a
        return render_template("prodotto_form.html", prodotto=None,
                               categorie=DB_tool.elenco_categorie(),
                               tag_disponibili=DB_tool.elenco_tag(),
                               tag_scelti=[])

    errore = _salva_prodotto(None)
    if errore:
        flash(errore, "errore")
        return redirect(url_for("nuovo_prodotto"))

    flash("Prodotto creato.", "ok")
    return redirect(url_for("gestione"))


@app.route("/gestione/prodotti/<int:prodotto_id>/modifica", methods=["GET", "POST"])
@gestore_richiesto
@csrf_richiesto
def modifica_prodotto(prodotto_id):
    scheda = DB_tool.prodotto_per_id(prodotto_id)
    if scheda is None:
        abort(404)

    if request.method == "GET":
        # MODIFICA 4b
        return render_template("prodotto_form.html", prodotto=scheda,
                               categorie=DB_tool.elenco_categorie(),
                               tag_disponibili=DB_tool.elenco_tag(),
                               tag_scelti=[t["nome"] for t in DB_tool.tag_prodotto(prodotto_id)])

    errore = _salva_prodotto(prodotto_id)
    if errore:
        flash(errore, "errore")
        return redirect(url_for("modifica_prodotto", prodotto_id=prodotto_id))

    flash("Prodotto aggiornato.", "ok")
    return redirect(url_for("gestione"))


@app.route("/gestione/prodotti/<int:prodotto_id>/elimina", methods=["POST"])
@gestore_richiesto
@csrf_richiesto
def elimina_prodotto(prodotto_id):
    scheda = DB_tool.prodotto_per_id(prodotto_id)
    if scheda is None:
        abort(404)

    DB_tool.elimina_prodotto(prodotto_id)
    if scheda["immagine_id"]:
        DB_tool.elimina_immagine(scheda["immagine_id"])
    DB_tool.log(sessione_valida()["utente_id"], "eliminazione", "prodotti",
                prodotto_id, scheda["nome"])
    flash("Prodotto eliminato.", "ok")
    return redirect(url_for("gestione"))


@app.route("/gestione/utenti/<int:utente_id>/ruolo", methods=["POST"])
@gestore_richiesto
@csrf_richiesto
def cambia_ruolo(utente_id):
    ruolo = request.form.get("ruolo")
    if ruolo not in ("base", "gestore"):
        abort(400)

    if utente_id == sessione_valida()["utente_id"] and ruolo == "base":
        flash("Non puoi togliere il ruolo a te stesso mentre sei collegato.", "errore")
        return redirect(url_for("gestione"))

    DB_tool.cambia_ruolo(utente_id, ruolo)
    DB_tool.log(sessione_valida()["utente_id"], "ruolo", "utenti", utente_id, ruolo)
    flash("Ruolo aggiornato.", "ok")
    return redirect(url_for("gestione"))


@app.route("/gestione/utenti/<int:utente_id>/elimina", methods=["POST"])
@gestore_richiesto
@csrf_richiesto
def elimina_utente(utente_id):
    if utente_id == sessione_valida()["utente_id"]:
        flash("Non puoi eliminare il tuo stesso account.", "errore")
        return redirect(url_for("gestione"))

    # MODIFICA 5: non restare senza gestori
    utente = DB_tool.utente_per_id(utente_id)
    if utente and utente["ruolo"] == "gestore" and DB_tool.conta_gestori() <= 1:
        flash("È l'unico gestore: promuovine un altro prima di eliminarlo.", "errore")
        return redirect(url_for("gestione"))

    DB_tool.elimina_utente(utente_id)
    DB_tool.log(sessione_valida()["utente_id"], "eliminazione", "utenti", utente_id,
                utente["email"] if utente else "")
    flash("Utente eliminato.", "ok")
    return redirect(url_for("gestione"))


# ---------------- SERVIZIO IMMAGINI ----------------

@app.route("/immagine/<int:immagine_id>")
@token_richiesto
def immagine(immagine_id):
    riga = DB_tool.immagine_per_id(immagine_id)
    if riga is None:
        abort(404)
    return send_file(io.BytesIO(riga["dati"]), mimetype=riga["mime"], max_age=86400)


# ---------------- SUPPORTO ----------------

def leggi_immagine(campo="immagine"):
    file = request.files.get(campo)
    if file is None or not file.filename:
        return None, None

    mime = file.mimetype
    if mime not in MIME_IMMAGINI:
        return None, "Formato non supportato: usa PNG, JPEG, GIF o WEBP."

    contenuto = file.read()
    if len(contenuto) > 3 * 1024 * 1024:
        return None, "Immagine troppo grande (massimo 3 MB)."
    if not contenuto.startswith(MIME_IMMAGINI[mime]):
        return None, "Il contenuto del file non corrisponde al formato dichiarato."
    if mime == "image/webp" and contenuto[8:12] != b"WEBP":
        return None, "File WEBP non valido."

    return (file.filename, mime, contenuto), None


def _salva_prodotto(prodotto_id):
    nome = (request.form.get("nome") or "").strip()
    descrizione = (request.form.get("descrizione") or "").strip()
    prezzo = request.form.get("prezzo", type=float)
    categoria_id = request.form.get("categoria_id", type=int)
    sessione = sessione_valida()

    if len(nome) < 2:
        return "Il nome del prodotto è troppo corto."
    if prezzo is None or prezzo < 0:
        return "Prezzo non valido."
    if categoria_id is None:
        return "Seleziona una categoria."

    immagine, errore = leggi_immagine()
    if errore:
        return errore

    immagine_id = None
    if immagine:
        immagine_id = DB_tool.salva_immagine(*immagine, sessione["utente_id"])

    # MODIFICA 6: la relazione N:M si riscrive a ogni salvataggio
    tag = request.form.getlist("tag")

    if prodotto_id is None:
        nuovo = DB_tool.crea_prodotto(nome, descrizione, prezzo, categoria_id,
                                      immagine_id, sessione["utente_id"])
        DB_tool.salva_tag_prodotto(nuovo, tag)
        DB_tool.log(sessione["utente_id"], "creazione", "prodotti", nuovo, nome)
    else:
        DB_tool.aggiorna_prodotto(prodotto_id, nome, descrizione, prezzo,
                                  categoria_id, immagine_id)
        DB_tool.salva_tag_prodotto(prodotto_id, tag)
        DB_tool.log(sessione["utente_id"], "modifica", "prodotti", prodotto_id, nome)

    return None


@app.errorhandler(403)
def errore_403(_):
    return render_template("errore.html", codice=403,
                           titolo="Accesso negato",
                           testo="Questa sezione è riservata agli utenti gestori."), 403


@app.errorhandler(404)
def errore_404(_):
    return render_template("errore.html", codice=404,
                           titolo="Pagina non trovata",
                           testo="L'indirizzo richiesto non esiste."), 404


@app.errorhandler(413)
def errore_413(_):
    return render_template("errore.html", codice=413,
                           titolo="File troppo grande",
                           testo="Il caricamento supera il limite di 5 MB."), 413


@app.errorhandler(400)
def errore_400(errore):
    return render_template("errore.html", codice=400,
                           titolo="Richiesta non valida",
                           testo=getattr(errore, "description", "Dati mancanti o corrotti.")), 400


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "5000")),
            debug=True)