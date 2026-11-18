# Aurora Tecnologie — catalogo interno

Applicazione Flask con autenticazione a due ruoli, verifica email,
catalogo prodotti con voti, upload immagini su database e registro attività.

## Requisiti

- Python 3.10+
- MySQL 8 / MariaDB

## Installazione

1. `python -m venv venv && source venv/bin/activate` (Windows: `venv\Scripts\activate`)
2. `pip install -r requirements.txt`
3. `mysql -u root -p < schema.sql`
4. Copia `.env.example` in `.env` e compila i valori reali
5. `python seed.py`
6. `python sviluppo_web.py` → http://127.0.0.1:5000

## Account demo

| Ruolo | Email | Password |
|---|---|---|
| gestore | gestore@auroratecnologie.it | Gestore!2026 |
| base | mario.rossi@example.it | Base!2026 |

## Scelte tecniche

**Password.** PBKDF2-HMAC-SHA256, 260 000 iterazioni, sale casuale per utente,
formato autodescrittivo `algoritmo$iterazioni$sale$digest` per poter migrare
l'algoritmo senza invalidare gli hash. Il confronto usa `hmac.compare_digest`.

**SQL injection.** Nessuna query costruita per concatenazione: solo segnaposto
`%s` con parametri separati. Le uniche stringhe interpolate sono nomi di tabella
in `seed.py`, presi da una lista chiusa.

**Autorizzazione a due livelli.** `token_richiesto` per gli utenti autenticati,
`gestore_richiesto` per le route CRUD. Le route pubbliche sono solo login,
registrazione e conferma.

**CSRF.** Token per sessione, confronto a tempo costante, obbligatorio su ogni POST.

**Token di sessione.** `secrets.token_urlsafe(32)`, salvati lato server con
scadenza a 30 minuti, cookie `HttpOnly` + `SameSite=Lax`. Nel database non
finisce mai un token in chiaro: la verifica email usa l'impronta SHA-256.

**Immagini.** Salvate come `LONGBLOB` con controllo dei magic bytes, non solo del
MIME dichiarato dal client. Limite 3 MB per file, 5 MB per richiesta.

**Schema.** Relazioni 1:N (`ruoli` → `utenti`, `categorie` → `prodotti`),
1:1 (`utenti` → `profili`), N:M (`prodotti` ↔ `tag`). Tutte le collation sono
`utf8mb4_unicode_ci`.

**Audit.** Ogni mutazione scrive in `audit_log` con utente, azione, entità e dettaglio.

## Struttura

- `sviluppo_web.py` — route e validazione
- `DB_tool.py` — unico accesso al database
- `sicurezza.py` — hashing e token
- `email_tool.py` — invio SMTP
- `dati.py` — contenuti del profilo aziendale

## Limiti noti

- I token di sessione vivono in memoria: un riavvio disconnette tutti.
- `/immagine/<id>` è raggiungibile senza login (URL non indovinabile solo per
  convenzione, gli ID sono sequenziali).