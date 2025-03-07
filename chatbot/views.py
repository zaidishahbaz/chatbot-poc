from django.utils.decorators import method_decorator  # type: ignore
from django.views.decorators.csrf import csrf_exempt  # type: ignore
from rest_framework import status  # type: ignore
from rest_framework.response import Response  # type: ignore
from rest_framework.views import APIView  # type: ignore
from transformers import pipeline  # type: ignore
from twilio.twiml.messaging_response import MessagingResponse  # type: ignore

from .models import ChatMessage
from .serializers import ChatMessageSerializer
from .utils import send_whatsapp_message


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
        message = request.data.get("Body")

        # Generate AI response in Hindi
        response_text = generate_hindi_response(message)

        # Save the chat in the database
        _ = ChatMessage.objects.create(
            sender=sender, message=message, response=response_text
        )

        # Send the AI response back to the user
        send_whatsapp_message(sender, response_text)

        # Twilio-compatible response
        twilio_response = MessagingResponse()
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
