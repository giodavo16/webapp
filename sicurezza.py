"""Hashing password e token. Nessuna dipendenza esterna."""

import hashlib
import hmac
import secrets

# PBKDF2-HMAC-SHA256: più robusto di md5/sha256 nudi, senza librerie aggiuntive.
ITERAZIONI = 260_000
ALGORITMO = "pbkdf2_sha256"


def genera_hash(password: str) -> str:
    """Restituisce 'algoritmo$iterazioni$sale$digest' in esadecimale."""
    sale = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), sale.encode("utf-8"), ITERAZIONI
    )
    return f"{ALGORITMO}${ITERAZIONI}${sale}${digest.hex()}"


def verifica_password(password: str, hash_salvato: str) -> bool:
    """Confronto a tempo costante: non rivela quanti caratteri sono corretti."""
    if not password or not hash_salvato:
        return False
    try:
        algoritmo, iterazioni, sale, atteso = hash_salvato.split("$")
        iterazioni = int(iterazioni)
    except (ValueError, AttributeError):
        return False
    if algoritmo != ALGORITMO:
        return False
    calcolato = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), sale.encode("utf-8"), iterazioni
    ).hex()
    return hmac.compare_digest(calcolato, atteso)


def sha256(testo: str) -> str:
    """Impronta per i token di verifica: nel DB non finisce mai il token in chiaro."""
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


def genera_token_verifica() -> str:
    return secrets.token_urlsafe(32)