from base64 import b64encode

import requests
from django.conf import settings
from twilio.rest import Client


def send_whatsapp_message(to, message=None, file_path=None):
    """
    Sends a WhatsApp message using Twilio API.

    :param to: Recipient WhatsApp number (e.g., 'whatsapp:+1234567890')
    :param message: Message text
    """
    if not message and not file_path:
        return

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    ngrok_url = settings.NGROK_URL

    if message:
        message = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            body=message,
            to=to,
        )
        # TODO: Save chats in DB
        # _ = ChatMessage.objects.create(
        #     sender=sender, message=message, response=response_text
        # )

    elif file_path:
        message = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            media_url=f"{ngrok_url}/{file_path}",
            to=to,
        )

    return message.sid


def parse_media_uri(twilio_url: str):
    auth_str = f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}"
    auth_bytes = auth_str.encode("utf-8")
    auth_b64 = b64encode(auth_bytes).decode("utf-8")
    headers = {"Authorization": "Basic " + auth_b64}
    return requests.get(twilio_url, headers=headers).url
