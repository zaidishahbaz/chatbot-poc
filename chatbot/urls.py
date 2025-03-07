from django.urls import path

from .views import ChatHistoryView, SendMessageView, WhatsAppWebhook

urlpatterns = [
    path("whatsapp/", WhatsAppWebhook.as_view(), name="whatsapp_webhook"),
    path("chat-history/", ChatHistoryView.as_view(), name="chat_history"),
    path("send-message/", SendMessageView.as_view(), name="send_message"),
]
