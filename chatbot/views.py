import io
from urllib.request import urlopen

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from transformers import pipeline
from twilio.twiml.messaging_response import MessagingResponse

from ai.util import ConversationUtil

from .models import ChatMessage
from .serializers import ChatMessageSerializer
from .utils import parse_media_uri, send_whatsapp_message

# Temporary language preference store (consider moving to DB)
user_language_preferences = {}

# Neeraj to provide the list of languages
LANGUAGE_CHOICES = {
    "1": "en",
    "2": "es",
    "3": "fr",
    "4": "hi",
}


def generate_hindi_response(message: str) -> str:
    """
    Generate an AI response in Hindi using a Hugging Face model.
    """
    generator = pipeline("text-generation", model="aashay96/indic-gpt")
    prompt = f"यूज़र: {message}\nएआई: "
    result = generator(prompt, max_length=50, do_sample=True)
    response = result[0]["generated_text"].split("\n")[1]
    return response.strip()


@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhook(APIView):
    def post(self, request, *args, **kwargs):
        sender = request.data.get("From")
        message = request.data.get("Body", "").strip().lower()
        message_type = request.data.get("MessageType")

        util = ConversationUtil(user=sender.replace("whatsapp:", ""))
        twilio_response = MessagingResponse()

        if message_type == "text":
            if message in util.SERVICE_OPTION_MAP:
                message = util.translate(util.SERVICE_OPTION_MAP[message])

            language = util.translation_util._detect_language(message)
            update_msg = util.handle_update_user_preference(language)
            if update_msg:
                send_whatsapp_message(sender, util.translate(update_msg))

            ai_response, response_type = util.ai_response(message=message)
            send_whatsapp_message(sender, ai_response)

        elif message_type == "audio":
            media_url = parse_media_uri(request.data.get("MediaUrl0"))
            with urlopen(media_url) as response:
                audio = io.BytesIO(response.read())
                audio.name = "input.mp3"

            message = util.translation_util._transcribe(audio)
            language = util.translation_util._detect_language(message)
            update_msg = util.handle_update_user_preference(language)
            if update_msg:
                send_whatsapp_message(sender, util.translate(update_msg))

            ai_response, response_type = util.ai_response(
                message=message, media_url=media_url
            )

            if response_type == "audio":
                send_whatsapp_message(sender, file_path=ai_response)
            else:
                send_whatsapp_message(sender, message=ai_response)

        # Twilio expects a valid XML response even if we reply separately
        twilio_response.message("✅ Message received.")
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

    # TODO: Add authentication and permission classes

    def post(self, request, *args, **kwargs):
        recipient = request.data.get("to")  # Format: "whatsapp:+1234567890"
        message = request.data.get("message")  # Text message

        if not recipient or not message:
            return Response(
                {"error": "Missing 'to' or 'message' field"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            message_sid = send_whatsapp_message(recipient, message)
            return Response(
                {
                    "message_sid": message_sid,
                    "status": "Message sent successfully",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
