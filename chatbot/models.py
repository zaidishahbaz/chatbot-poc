from django.db import models


class ChatMessage(models.Model):
    sender = models.CharField(max_length=200)
    message = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.message}"
