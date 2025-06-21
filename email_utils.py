import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger("email_utils")


def send_email(
    subject: str,
    body: str,
    EMAIL_FROM: str,
    EMAIL_TO: str,
    SMTP_SERVER: str,
    SMTP_PORT: int,
    SMTP_USERNAME: str,
    SMTP_PASSWORD: str,
):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
