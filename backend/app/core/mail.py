import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from dotenv import load_dotenv

load_dotenv()

MAIL_PORT = os.environ.get("MAIL_PORT", 465)
try:
    MAIL_PORT = int(MAIL_PORT)
except ValueError:
    MAIL_PORT = 465

conf = ConnectionConfig(
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD", ""),
    MAIL_FROM=os.environ.get("MAIL_FROM", "noreply@moodle-agents.com"),
    MAIL_FROM_NAME=os.environ.get("MAIL_FROM_NAME", "System Agentowy Moodle"),
    MAIL_PORT=MAIL_PORT,
    MAIL_SERVER=os.environ.get("MAIL_SERVER", ""),
    MAIL_STARTTLS=os.environ.get("MAIL_STARTTLS", "False").lower() == "true",
    MAIL_SSL_TLS=os.environ.get("MAIL_SSL_TLS", "True").lower() == "true",
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_reset_password_email(email_to: EmailStr, token: str):

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5175")
    reset_link = f"{frontend_url}?token={token}"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #8B0002;">System Agentowy Moodle</h2>
        <p>Otrzymaliśmy prośbę o zresetowanie hasła dla Twojego konta.</p>
        <p>Kliknij poniższy przycisk, aby ustawić nowe hasło. Link jest ważny przez godzinę.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" style="background-color: #8B0002; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Zresetuj swoje hasło</a>
        </div>
        <p style="font-size: 12px; color: #666;">Jeśli przycisk nie działa, skopiuj ten link i wklej w przeglądarce:</p>
        <p style="font-size: 12px; color: #666; word-break: break-all;">{reset_link}</p>
        <p style="font-size: 12px; color: #666; margin-top: 30px;">Jeśli to nie Ty składałeś prośbę, zignoruj tę wiadomość.</p>
    </div>
    """

    message = MessageSchema(
        subject="Resetowanie hasła w Moodle AI",
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        print(f"Reset email sent to {email_to}")
    except Exception as e:
        print(f"Error sending reset email: {e}")
