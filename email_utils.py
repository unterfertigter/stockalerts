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
    """
    Send an email using SMTP with the given subject and body.
    Logs attempts, successes, and failures.
    """
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
