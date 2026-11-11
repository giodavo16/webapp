import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


def send_verification_email(email, verification_url):

    message = MIMEMultipart()

    message["From"] = os.getenv("MAIL_SENDER")
    message["To"] = email
    message["Subject"] = "Conferma il tuo account"

    body = f"""
    Ciao!

    Grazie per esserti registrato.

    Per attivare il tuo account clicca sul seguente link:

    {verification_url}

    Il link scadrà dopo 24 ore.

    Se non hai richiesto la registrazione, ignora questa email.
    """

    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(
            os.getenv("MAIL_SERVER"),
            int(os.getenv("MAIL_PORT", 587))
        ) as server:

            server.starttls()

            server.login(
                os.getenv("MAIL_USERNAME"),
                os.getenv("MAIL_PASSWORD")
            )

            server.send_message(message)

        return True

    except Exception as e:
        print("Errore invio email:", e)
        return False