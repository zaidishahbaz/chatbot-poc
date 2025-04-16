from django.db import models


class ChatMessage(models.Model):
    sender = models.CharField(max_length=200)
    message = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        truncated_message = (
            self.message[:50] + "..." if len(self.message) > 50 else self.message
        )
        return f"{self.sender}: {truncated_message}"
