import os
import logging
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.database.models import CarListing

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASSWORD", "")
        self.notification_email = os.getenv("NOTIFICATION_EMAIL", "")

    def notify_top_deal(self, car: CarListing, reason: str = "TOP DEAL"):
        title = f"🚗 Auto-Agent: {reason} - {car.make} {car.model}"
        msg = (
            f"**{reason}: {car.title}**\n\n"
            f"• Preis: {int(car.price):,} EUR\n"
            f"• Deal-Score: **{car.deal_score} / 100**\n"
            f"• Kilometerstand: {car.mileage:,} km | EZ: {car.first_registration_year} | {car.power_hp} PS\n"
            f"• Standort: {car.city} (~{round(car.distance_km, 1)} km entfernt)\n"
            f"• Quelle: {car.provider}\n"
            f"• Link: {car.url}\n"
        ).replace(",", ".")

        logger.info(f"Verschicke Benachrichtigung für {car.title}...")
        self._send_discord(title, msg)
        self._send_email(title, msg)

    def _send_discord(self, title: str, content: str):
        if not self.discord_webhook:
            return
        payload = {
            "username": "Auto-Agent",
            "content": f"### {title}\n{content}"
        }
        try:
            res = requests.post(self.discord_webhook, json=payload, timeout=5)
            if res.status_code not in (200, 204):
                logger.warning(f"Discord Webhook Status: {res.status_code}")
        except Exception as e:
            logger.error(f"Fehler beim Senden an Discord: {e}")

    def _send_email(self, subject: str, content: str):
        if not self.smtp_host or not self.notification_email:
            return
        try:
            msg = MIMEMultipart()
            msg["From"] = self.smtp_user or "auto-agent@local"
            msg["To"] = self.notification_email
            msg["Subject"] = subject
            msg.attach(MIMEText(content, "plain", "utf-8"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                if self.smtp_user and self.smtp_pass:
                    server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            logger.info("E-Mail-Benachrichtigung erfolgreich zugestellt.")
        except Exception as e:
            logger.error(f"Fehler beim Senden der E-Mail: {e}")