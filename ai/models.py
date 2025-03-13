# Create your models here.
from django.db import models


class SessionRole(models.TextChoices):
    USER = "user"
    ASSISTANT = "assistant"
    DEVELOPER = "developer"
    SYSTEM = "system"


class Languages(models.TextChoices):
    ENGLISH = "en"
    SPANISH = "es"
    HINDI = "hi"
    FRENCH = "fr"
    NEPALI = "ne"
    GERMAN = "ge"
    JAPANESE = "ja"


class UserPreference(models.Model):
    user = models.CharField(max_length=15)
    language = models.CharField(max_length=20, choices=Languages.choices)


class OpenAiConvSession(models.Model):
    user = models.CharField(max_length=15)
    message = models.TextField()
    role = models.CharField(max_length=10, choices=SessionRole.choices)
    created_date = models.DateTimeField(auto_created=True, auto_now=True)
