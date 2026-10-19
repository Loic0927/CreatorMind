import os
import smtplib
from email.message import EmailMessage

from backend.config import is_production


class EmailDeliveryError(RuntimeError):
    pass


def send_login_code(email: str, code: str) -> None:
    host = os.getenv("POSTBRIDGE_SMTP_HOST", "").strip()
    sender = os.getenv("POSTBRIDGE_EMAIL_FROM", "").strip()
    if not host or not sender:
        if is_production():
            raise EmailDeliveryError("Email login is not configured.")
        return

    message = EmailMessage()
    message["Subject"] = "Your PostBridge sign-in code"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Your PostBridge sign-in code is {code}. It expires in 10 minutes.\n\n"
        "If you did not request this code, you can ignore this email."
    )

    port = int(os.getenv("POSTBRIDGE_SMTP_PORT", "587"))
    username = os.getenv("POSTBRIDGE_SMTP_USERNAME", "")
    password = os.getenv("POSTBRIDGE_SMTP_PASSWORD", "")
    use_ssl = os.getenv("POSTBRIDGE_SMTP_SSL", "false").lower() == "true"
    try:
        client_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with client_class(host, port, timeout=15) as client:
            if not use_ssl:
                client.starttls()
            if username:
                client.login(username, password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise EmailDeliveryError("PostBridge could not send the sign-in email.") from None
