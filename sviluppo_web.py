import secrets
import time
from functools import wraps
from uuid import uuid4

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

import DB_tool

app = Flask(__name__)

credenziali = {
    "ciccio": "pasticcio1",
}

DURATA_TOKEN = 60 * 30
token_attivi = {}
compilazioni = {}

INFO_AZIENDA = {
    "ragione_sociale": "Aurora Tecnologie S.p.A.",
    "claim": "Infrastrutture digitali che non si fermano mai.",
    "settore": "Servizi IT, cloud e integrazione di sistemi",
    "fondazione": "2009",
    "forma_giuridica": "Società per azioni",
    "partita_iva": "IT 04829120367",
    "codice_fiscale": "04829120367",
    "rea": "MO-418772",
    "capitale_sociale": "1.250.000 € interamente versato",
    "dipendenti": "184",
    "sede_legale": "Via dei Mille 42 — 41121 Modena (MO), Italia",
    "telefono": "+39 059 412 8877",
    "email": "info@auroratecnologie.it",
    "pec": "auroratecnologie@legalmail.it",
    "codice_sdi": "M5UXCR1",
    "orari": "Lunedì – Venerdì, 08:30 – 18:30",
    "descrizione": (
        "Aurora Tecnologie progetta, migra e presidia infrastrutture critiche per aziende "
        "manifatturiere, sanitarie e logistiche. Nata nel 2009 come piccolo studio di "
        "consulenza sistemistica, oggi gestisce ambienti cloud ibridi, reti industriali e "
        "servizi di continuità operativa per oltre 430 clienti in dodici Paesi."
    ),
}

SEZIONI_AZIENDA = [
    ("panoramica", "Panoramica"),
    ("storia", "Storia"),
    ("missione", "Missione"),
    ("valori", "Valori"),
    ("servizi", "Servizi"),
    ("numeri", "Numeri"),
    ("team", "Team"),
    ("sostenibilita", "Sostenibilità"),
    ("certificazioni", "Certificazioni"),
    ("sedi", "Sedi"),
    ("carriere", "Lavora con noi"),
    ("faq", "FAQ"),
    ("contatti", "Contatti"),
]

NUMERI = [
    ("184", "Persone in organico"),
    ("27,4 M€", "Fatturato 2024"),
    ("99,98%", "Uptime medio dei servizi gestiti"),
    ("12", "Paesi in cui operiamo"),
    ("430+", "Clienti attivi"),
    ("16", "Anni di attività"),
]

STORIA = [
    {"anno": "2009", "titolo": "Fondazione",
     "testo": "Tre sistemisti e un furgone di rack usati: Aurora nasce in un garage di Modena "
              "con i primi contratti di assistenza per PMI manifatturiere."},
    {"anno": "2012", "titolo": "Primo data center proprietario",
     "testo": "Entra in funzione la sala CED di 240 m² con gruppi di continuità ridondati N+1 "
              "e collegamento in fibra dedicata."},
    {"anno": "2015", "titolo": "ISO/IEC 27001",
     "testo": "Certifichiamo il sistema di gestione della sicurezza delle informazioni e "
              "apriamo la divisione dedicata alla compliance."},
    {"anno": "2018", "titolo": "Espansione europea",
     "testo": "Apre la sede di Lubiana; i servizi gestiti superano per la prima volta i "
              "confini nazionali con contratti in Slovenia, Austria e Croazia."},
    {"anno": "2021", "titolo": "Piattaforma Aurora Cloud",
     "testo": "Rilasciamo la piattaforma interna di orchestrazione multi-cloud, oggi usata da "
              "oltre 200 clienti per il provisioning self-service."},
    {"anno": "2023", "titolo": "Divisione sicurezza",
     "testo": "Nasce l'unità SOC con copertura 24/7 e servizi di threat hunting e risposta "
              "agli incidenti."},
    {"anno": "2025", "titolo": "184 persone, 12 Paesi",
     "testo": "Chiusura del bilancio a 27,4 milioni di euro e apertura del polo di ricerca su "
              "edge computing e reti industriali."},
]

VALORI = [
    ("Affidabilità", "Un fermo macchina costa più di qualsiasi licenza: progettiamo per la "
                     "ridondanza, non per il risparmio apparente."),
    ("Trasparenza", "Preventivi a corpo, nessun costo nascosto, report mensile con ore e "
                    "attività tracciate."),
    ("Competenza artigiana", "Team piccoli e stabili: il cliente parla sempre con chi mette "
                             "le mani sull'infrastruttura."),
    ("Sicurezza by design", "La postura di sicurezza si progetta in fase di architettura, "
                            "non si rattoppa dopo l'incidente."),
    ("Indipendenza tecnologica", "Nessuna esclusiva di vendor: scegliamo lo stack in base al "
                                 "problema, non al margine."),
    ("Continuità umana", "Formazione continua e turni sostenibili: nessuno in reperibilità per "
                         "30 giorni di fila."),
]

SERVIZI = [
    {"titolo": "Cloud e ambienti ibridi", "testo":
        "Migrazione, gestione e ottimizzazione di ambienti multi-cloud con orchestrazione "
        "automatica e cost governance.",
     "voci": ["Assessment e piano di migrazione", "Landing zone e IaC", "FinOps e controllo costi"]},
    {"titolo": "Infrastrutture critiche", "testo":
        "Progettazione di data center, ridondanza di rete e sistemi di continuità operativa "
        "con obiettivi di RTO/RPO contrattualizzati.",
     "voci": ["Sala CED e power design", "Disaster recovery testato due volte l'anno", "Reperibilità 24/7"]},
    {"titolo": "Cybersecurity e SOC", "testo":
        "Monitoraggio continuo, threat hunting e risposta agli incidenti da centro operativo di "
        "sicurezza con copertura integrale.",
     "voci": ["SIEM e correlazione log", "Endpoint detection & response", "Incident response e forensics"]},
    {"titolo": "Reti industriali e OT", "testo":
        "Segmentazione di reti di fabbrica, integrazione PLC/SCADA e connettività deterministica "
        "per linee produttive.",
     "voci": ["Segmentazione IT/OT", "Telemetria di linea", "Edge computing e raccolta dati"]},
    {"titolo": "Integrazione applicativa", "testo":
        "API gateway, middleware e automazione dei processi tra gestionali, MES e piattaforme di "
        "terze parti.",
     "voci": ["API management", "ETL e data integration", "Automazione RPA"]},
    {"titolo": "Gestione e supporto", "testo":
        "Servizi gestiti con SLA da 1 ora, monitoraggio proattivo e service desk con referente "
        "tecnico dedicato.",
     "voci": ["SLA 1h / 4h / NBD", "Monitoraggio proattivo", "Service desk italiano"]},
]

TEAM = [
    ("Elena Ruggeri", "Amministratrice delegata",
     "In Aurora dal 2011, guida la strategia e lo sviluppo internazionale."),
    ("Marco Bellini", "Direttore tecnico",
     "Co-fondatore, architetto delle piattaforme di continuità operativa."),
    ("Sara Nocentini", "Responsabile sicurezza",
     "Costruisce il SOC e i processi di incident response."),
    ("Davide Ferraro", "Responsabile cloud",
     "Coordina le migrazioni e i team di platform engineering."),
    ("Giulia Pavesi", "Direttrice amministrativa",
     "Bilancio, controllo di gestione e rapporti con gli istituti di credito."),
    ("Andrea Costa", "Responsabile persone",
     "Selezione, formazione e politiche di benessere interno."),
]

SOSTENIBILITA = [
    ("-62%", "Emissioni Scope 1 e 2 rispetto al 2019"),
    ("100%", "Energia da fonti rinnovabili certificate GO"),
    ("PUE 1,28", "Efficienza media del data center di Modena"),
]

CERTIFICAZIONI = [
    ("ISO/IEC 27001:2022", "Sicurezza delle informazioni", "dal 2015"),
    ("ISO 9001:2015", "Sistema di gestione della qualità", "dal 2012"),
    ("ISO 14001:2015", "Gestione ambientale", "dal 2019"),
    ("ISO 22301:2019", "Continuità operativa", "dal 2021"),
    ("SOC 2 Type II", "Controlli su sicurezza e disponibilità", "dal 2022"),
]

SEDI = [
    ("Modena", "Sede legale e data center", "Via dei Mille 42, 41121 Modena (MO)", "Italia"),
    ("Milano", "Ufficio commerciale", "Via Tortona 27, 20144 Milano (MI)", "Italia"),
    ("Bologna", "Polo ricerca e sviluppo", "Via Stalingrado 71, 40128 Bologna (BO)", "Italia"),
    ("Lubiana", "Filiale estera", "Dunajska cesta 156, 1000 Lubiana", "Slovenia"),
]

BENEFIT = [
    "Contratto a tempo indeterminato con CCNL Commercio, terzo livello o superiore",
    "Buoni pasto da 8 € e welfare aziendale fino a 800 € annui",
    "Formazione certificata pagata e 40 ore annue di studio retribuito",
    "Smart working ibrido fino a 3 giorni a settimana",
    "Reperibilità volontaria con indennizzo e recupero garantito",
    "Fondo sanitario integrativo esteso al nucleo familiare",
]

POSIZIONI = [
    ("System Engineer Linux", "Modena · Ibrido",
     "Gestione di cluster Kubernetes e automazione infrastrutturale."),
    ("Analista SOC (turni)", "Bologna · In sede",
     "Monitoraggio, triage e risposta a incidenti su infrastrutture critiche."),
    ("Network Engineer OT", "Modena · Trasferte 20%",
     "Segmentazione di reti industriali e integrazione PLC/SCADA."),
    ("Developer Python", "Milano · Ibrido",
     "Sviluppo di tooling interno per la piattaforma Aurora Cloud."),
]

FAQ = [
    ("Con quali clienti lavorate?",
     "Per il 68% PMI manifatturiere con 50-500 dipendenti, per il 21% strutture sanitarie e "
     "società di logistica, per l'11% enti pubblici e università."),
    ("Qual è la dimensione media di un progetto?",
     "Gli interventi di migrazione e infrastruttura si collocano tra 40.000 e 600.000 €, con "
     "contratti di gestione pluriennali a partire da 1.800 € al mese."),
    ("Lavorate solo in Italia?",
     "No. La sede legale e il data center primario sono a Modena, ma operiamo in dodici Paesi "
     "con filiale diretta a Lubiana e partner certificati in Austria, Croazia e Ungheria."),
    ("Come gestite i dati dei clienti?",
     "Tutti i dati restano su infrastrutture in UE, con cifratura at rest e in transito, "
     "classificazione documentale e registro dei trattamenti aggiornato."),
    ("Offrite ambienti di test?",
     "Sì: ogni progetto include un ambiente di staging identico alla produzione e un piano di "
     "collaudo con test di ripristino documentati."),
    ("Come si avvia una collaborazione?",
     "Primo incontro conoscitivo gratuito, assessment di 5 giorni lavorativi, poi preventivo a "
     "corpo con tempi e responsabilità definite."),
]

@app.context_processor
def inietta_dati_azienda():
    """Rende i dati del profilo aziendale disponibili in ogni template."""
    return {
        "azienda": INFO_AZIENDA,
        "sezioni": SEZIONI_AZIENDA,
        "numeri": NUMERI,
        "storia": STORIA,
        "valori": VALORI,
        "servizi": SERVIZI,
        "team": TEAM,
        "sostenibilita": SOSTENIBILITA,
        "certificazioni": CERTIFICAZIONI,
        "sedi": SEDI,
        "benefit": BENEFIT,
        "posizioni": POSIZIONI,
        "faq": FAQ,
    }

#  AUTENTICAZIONE

def genera_token(username):
    token = secrets.token_urlsafe(32)

    token_attivi[token] = {
        "username": username,
        "scadenza": time.time() + DURATA_TOKEN,
    }

    return token

def leggi_token(token):
    if not token:
        return None

    dati = token_attivi.get(token)

    if dati is None:
        return None

    if dati["scadenza"] < time.time():
        token_attivi.pop(token, None)
        return None

    return dati

def token_richiesto(funzione):
    @wraps(funzione)
    def wrapper(*args, **kwargs):
        token = (
            request.args.get("token")
            or request.form.get("token")
        )

        if leggi_token(token) is None:
            return redirect(url_for("login", errore="sessione"))

        return funzione(*args, **kwargs)

    return wrapper

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET"])
def login():
    # token=None -> la card di accesso viene mostrata
    return render_template(
        "login.html",
        token=None,
        username=None,
        errore=request.args.get("errore"),
    )

@app.route("/api/login", methods=["POST"])
def api_login():
    dati = request.get_json(silent=True) or request.form

    username = (dati.get("username") or "").strip()
    password = dati.get("password") or ""

    if credenziali.get(username) != password:
        return jsonify({
            "success": False,
            "messaggio": "Username o password errati.",
        }), 401

    token = genera_token(username)

    return jsonify({
        "success": True,
        "token": token,
        "redirect": url_for("dashboard", token=token),
    }), 200

@app.route("/logout", methods=["GET", "POST"])
def logout():
    token = (
        request.args.get("token")
        or request.form.get("token")
    )

    if token:
        token_attivi.pop(token, None)

    return redirect(url_for("login"))

@app.route("/form", methods=["GET"])
@token_richiesto
def mostra_form():
    token = request.args.get("token")

    return render_template("form.html", token=token)


@app.route("/dashboard", methods=["GET"])
@token_richiesto
def dashboard():

    token = request.args.get("token") or request.form.get("token")

    ricerca = request.args.get("q", "").strip()

    if ricerca:
        risultati = DB_tool.cerca_prodotti(ricerca)
    else:
        risultati = DB_tool.visualizza_prodotti()

    return render_template(
        "dashboard.html",
        token=token,
        username=leggi_token(token)["username"],
        prodotti=risultati,
        ricerca=ricerca,
    )


@app.route("/azienda", methods=["GET"])
@token_richiesto
def azienda():
    """Profilo aziendale completo, con le sezioni navigabili dalla navbar.

    Usa lo stesso template del login: la card di accesso viene nascosta
    perché qui il token è presente.
    """
    token = request.args.get("token") or request.form.get("token")

    return render_template(
        "login.html",
        token=token,
        username=leggi_token(token)["username"],
        errore=None,
    )

@app.route("/submit", methods=["POST"])
@token_richiesto
def submit_form():
    nome = request.form.get("nome", "").strip()
    data = request.form.get("data", "")
    genere = request.form.get("genere", "")
    newsletter = request.form.get("newsletter") == "on"

    compilazione_id = str(uuid4())

    compilazioni[compilazione_id] = {
        "nome": nome,
        "data": data,
        "genere": genere,
        "newsletter": newsletter,
    }

    return redirect(
        url_for("riepilogo", compilazione_id=compilazione_id),
        code=303,
    )

@app.route("/riepilogo/<compilazione_id>", methods=["GET"])
def riepilogo(compilazione_id):
    dati = compilazioni.get(compilazione_id)

    if dati is None:
        return jsonify({
            "success": False,
            "messaggio": "Compilazione non trovata",
        }), 404

    return jsonify({
        "success": True,
        "messaggio": "Form compilato correttamente",
        "dati": dati,
    }), 200

if __name__ == "__main__":
    app.run(debug=True)