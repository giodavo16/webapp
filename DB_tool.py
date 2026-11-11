import os
import mysql.connector
from mysql.connector import Error, IntegrityError
from dotenv import load_dotenv

# CARICAMENTO CONFIGURAZIONE
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

# CONNESSIONE DATABASE

def connetti():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        if conn.is_connected():
            return conn

        conn.close()
        return None

    except Error as e:
        print(f"Errore di connessione: {e}")
        return None

# LETTURA PRODOTTI

def visualizza_prodotti():

    sql = """
        SELECT id, prodotto, prezzo, categoria
        FROM prodotti
        ORDER BY id
    """

    conn = connetti()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        return cursor.fetchall()

    except Error as e:
        print(f"Errore durante la lettura: {e}")
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()

# RICERCA PRODOTTI

def cerca_prodotti(ricerca):

    sql = """
        SELECT id, prodotto, prezzo, categoria
        FROM prodotti
        WHERE CAST(id AS CHAR) LIKE %s
        OR prodotto LIKE %s
        OR CAST(prezzo AS CHAR) LIKE %s
        OR categoria LIKE %s
        ORDER BY id
    """

    conn = connetti()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        valore = f"%{ricerca}%"

        cursor.execute(
            sql,
            (valore, valore, valore, valore)
        )

        return cursor.fetchall()

    except Error as e:
        print(f"Errore durante la ricerca: {e}")
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()

# REGISTRAZIONE NUOVO UTENTE

def crea_utente(nome, email, password_hash, token_hash):

    sql = """
        INSERT INTO users (
            name,
            email,
            password_hash,
            is_verified,
            verification_token_hash,
            verification_expires_at
        )
        VALUES (%s, %s, %s, FALSE, %s,
                DATE_ADD(UTC_TIMESTAMP(), INTERVAL 24 HOUR))
    """

    conn = connetti()

    if conn is None:
        return None

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute(
            sql,
            (nome, email, password_hash, token_hash)
        )

        conn.commit()

        return cursor.lastrowid

    except IntegrityError:
        conn.rollback()
        print("Email già registrata.")
        return None

    except Error as e:
        conn.rollback()
        print(f"Errore durante la registrazione: {e}")
        return None

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()

# RECUPERO UTENTE TRAMITE EMAIL

def recupera_utente(email):

    conn = connetti()

    if conn is None:
        return None

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        return cursor.fetchone()

    except Error as e:
        print(f"Errore recupero utente: {e}")
        return None

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()

# VERIFICA E ATTIVAZIONE ACCOUNT

def verifica_utente(token_hash):

    conn = connetti()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        sql = """
            UPDATE users
            SET is_verified = TRUE,
                verification_token_hash = NULL,
                verification_expires_at = NULL
            WHERE verification_token_hash = %s
              AND is_verified = FALSE
              AND verification_expires_at > UTC_TIMESTAMP()
        """

        cursor.execute(sql, (token_hash,))
        conn.commit()

        return cursor.rowcount == 1

    except Error as e:
        conn.rollback()
        print(f"Errore durante la verifica: {e}")
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()