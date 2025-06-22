import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger("email_utils")

EMAIL_CONFIG = {}


def set_email_config(
    EMAIL_FROM: str,
    EMAIL_TO: str,
    SMTP_SERVER: str,
    SMTP_PORT: int,
    SMTP_USERNAME: str,
    SMTP_PASSWORD: str,
):
    global EMAIL_CONFIG
    EMAIL_CONFIG = {
        "EMAIL_FROM": EMAIL_FROM,
        "EMAIL_TO": EMAIL_TO,
        "SMTP_SERVER": SMTP_SERVER,
        "SMTP_PORT": SMTP_PORT,
        "SMTP_USERNAME": SMTP_USERNAME,
        "SMTP_PASSWORD": SMTP_PASSWORD,
    }


def send_email(subject: str, body: str):
    cfg = EMAIL_CONFIG
    logger.info(f"Attempting to send email to {cfg['EMAIL_TO']} with subject: '{subject}'")
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = cfg["EMAIL_FROM"]
    msg["To"] = cfg["EMAIL_TO"]
    try:
        with smtplib.SMTP(cfg["SMTP_SERVER"], cfg["SMTP_PORT"]) as server:
            server.starttls()
            server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            server.sendmail(cfg["EMAIL_FROM"], cfg["EMAIL_TO"], msg.as_string())
        logger.info(f"Email sent successfully to {cfg['EMAIL_TO']} with subject: '{subject}'")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {cfg['EMAIL_TO']} with subject: '{subject}': {e}")
    except Exception as e:
        logger.error(
            f"Unexpected error sending email to {cfg['EMAIL_TO']} with subject: '{subject}': {e}", exc_info=True
        )
