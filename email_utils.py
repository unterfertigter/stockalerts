import logging
import os
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Ensure all required environment variables are set
if not all([EMAIL_TO, EMAIL_FROM, SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD]):
    raise Exception("Missing required email environment variables.")


def send_email(subject: str, body: str):
    logger.info(f"Attempting to send email to {EMAIL_TO} with subject: '{subject}'")
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        logger.info(f"Email sent successfully to {EMAIL_TO} with subject: '{subject}'")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {EMAIL_TO} with subject: '{subject}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending email to {EMAIL_TO} with subject: '{subject}': {e}", exc_info=True)
