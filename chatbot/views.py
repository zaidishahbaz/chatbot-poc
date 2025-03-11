from django.utils.decorators import method_decorator  # type: ignore
from django.views.decorators.csrf import csrf_exempt  # type: ignore
from rest_framework import status  # type: ignore
from rest_framework.response import Response  # type: ignore
from rest_framework.views import APIView  # type: ignore
from transformers import pipeline  # type: ignore
from twilio.twiml.messaging_response import MessagingResponse

from ai.util import ConversationUtil  # type: ignore

from .models import ChatMessage
from .serializers import ChatMessageSerializer
from .utils import parse_media_uri, send_whatsapp_message

# Temporary dictionary to store user language preferences (better to use a database)
user_language_preferences: dict = {}

# Language options mapping
LANGUAGE_CHOICES = {
    "1": "en",  # English
    "2": "es",  # Spanish
    "3": "fr",  # French
    "4": "hi",  # Hindi
}


def generate_hindi_response(message):
    """
    Generates an AI-based Hindi response using a free Hugging Face model.
    """
    generator = pipeline("text-generation", model="aashay96/indic-gpt")

    # Prompting the model to generate a relevant response in Hindi
    prompt = f"यूज़र: {message}\nएआई: "

    result = generator(prompt, max_length=50, do_sample=True)

    ai_response = result[0]["generated_text"].split("\n")[1]  # Extract AI response

    return ai_response.strip()


@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhook(APIView):
    def post(self, request, *args, **kwargs):
        sender = request.data.get("From")
        message = request.data.get("Body", "").strip().lower()  # Normalize message
        message_type = request.data.get("MessageType")

        util = ConversationUtil()
        twilio_response = MessagingResponse()
        response_text = message  # Default response
        destination_lang = "fr"

        if message_type == "text":
            # Handle language selection
            if message in LANGUAGE_CHOICES:
                user_language_preferences[sender] = LANGUAGE_CHOICES[message]
                lang_name = {
                    "en": "English",
                    "es": "Spanish",
                    "fr": "French",
                    "hi": "Hindi",
                }[LANGUAGE_CHOICES[message]]
                message_response = (
                    f"✅ Your preferred language has been set to {lang_name}."
                )

            # Handle language change request
            elif message in ["change language", "set language", "update language"]:
                message_response = "Please select your new preferred language:\n1️⃣ English\n2️⃣ Spanish\n3️⃣ French\n4️⃣ Hindi\n\nReply with the number of your choice."

            # Handle initial greeting
            elif message == "hi" and sender not in user_language_preferences:
                message_response = "Hello! Please select your preferred language:\n1️⃣ English\n2️⃣ Spanish\n3️⃣ French\n4️⃣ Hindi\n\nReply with the number of your choice."

            else:
                # Get user's preferred language (default to English)
                destination_lang = user_language_preferences.get(sender, "en")
                message_response = util.ai_response(message=message)

            # Translate response if language is set
            if destination_lang != "en":
                response_text = util.text_to_text(
                    message_response,
                    source_lang="en",
                    destination_lang=destination_lang,
                )
                send_whatsapp_message(sender, response_text)

            send_whatsapp_message(sender, message_response)

        elif message_type == "audio":
            media_url = parse_media_uri(request.data.get("MediaUrl0"))
            output = util.speech_to_speech(
                media_url, source_lang="en", destination_lang="fr"
            )
            send_whatsapp_message(sender, file_path=output)

        twilio_response.message(response_text)
        return Response(
            str(twilio_response), content_type="text/xml", status=status.HTTP_200_OK
        )


class ChatHistoryView(APIView):
    def get(self, request):
        messages = ChatMessage.objects.all().order_by("-timestamp")
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SendMessageView(APIView):
    """
    API endpoint to send a WhatsApp message from the backend.
    """

    def post(self, request, *args, **kwargs):
        recipient = request.data.get(
            "to"
        )  # WhatsApp number (e.g., "whatsapp:+1234567890")
        message = request.data.get("message")  # Message text

        if not recipient or not message:
            return Response(
                {"error": "Missing 'to' or 'message' field"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            message_sid = send_whatsapp_message(recipient, message)
            return Response(
                {"message_sid": message_sid, "status": "Message sent successfully"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
