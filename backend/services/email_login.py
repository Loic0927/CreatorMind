import hashlib
import hmac
import os
import smtplib
from email.message import EmailMessage

from backend.config import is_production


class EmailDeliveryError(RuntimeError):
    pass


def reviewer_login_enabled_for(email: str) -> bool:
    """Return whether the narrowly scoped App Review login is active.

    This is deliberately opt-in only when *both* configuration values are set,
    and callers pass normalized email addresses.  Keeping the check here makes
    it impossible for the email sender and verifier to drift apart.
    """

    configured_email = os.getenv("POSTBRIDGE_REVIEW_LOGIN_EMAIL", "").strip()
    configured_hash = os.getenv("POSTBRIDGE_REVIEW_LOGIN_CODE_HASH", "").strip()
    return bool(
        configured_email and configured_hash and hmac.compare_digest(configured_email.casefold(), email.casefold())
    )


def reviewer_login_code_matches(code: str) -> bool:
    configured_hash = os.getenv("POSTBRIDGE_REVIEW_LOGIN_CODE_HASH", "").strip()
    if not configured_hash:
        return False
    calculated = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()
    return hmac.compare_digest(configured_hash, calculated)


def send_login_code(email: str, code: str) -> None:
    # Meta and Apple reviewers cannot receive a one-time email.  The code is
    # verified separately against a configured hash; never emit it here.
    if reviewer_login_enabled_for(email):
        return
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
