from django.conf import settings
from twilio.rest import Client


def send_whatsapp_message(to, message):
    """
    Sends a WhatsApp message using Twilio API.

    :param to: Recipient WhatsApp number (e.g., 'whatsapp:+1234567890')
    :param message: Message text
    """
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    message = client.messages.create(
        from_=settings.TWILIO_WHATSAPP_NUMBER, body=message, to=to
    )

    return message.sid
