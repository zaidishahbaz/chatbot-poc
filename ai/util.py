import io
import logging
import os
import uuid
from urllib.request import urlopen

from django.conf import settings
from google.cloud.translate_v2 import Client
from openai import OpenAI

logger = logging.getLogger(__name__)


class ConversationUtil:
    open_ai_client: OpenAI
    translation_client: Client

    TRANSCRIPTION_SETTINGS = {"model": "whisper-1"}
    SPEECH_SETTINGS = {"model": "tts-1", "voice": "echo"}

    def __init__(self):
        self.open_ai_client = OpenAI(api_key=settings.OPEN_AI_KEY)
        self.translation_client = Client.from_service_account_info(
            settings.GOOGLE_SERVICE_JSON
        )

    def _transcribe(self, audio: io.BytesIO) -> str:
        transcription = self.open_ai_client.audio.translations.create(
            file=audio, **self.TRANSCRIPTION_SETTINGS
        )
        return transcription.text

    def _translate(
        self, source_text: str, source_lang: str, destination_lang: str
    ) -> str:
        result = self.translation_client.translate(
            source_text,
            source_language=source_lang,
            target_language=destination_lang,
        )
        return result["translatedText"]

    def _generate_audio(self, input: str):

        with self.open_ai_client.audio.speech.with_streaming_response.create(
            **self.SPEECH_SETTINGS, input=input
        ) as response:
            file_name = f"{str(uuid.uuid4()).replace('-', '')}.mp3"
            file_path = os.path.join(settings.MEDIA_ROOT, file_name)
            response.stream_to_file(file_path)
            return file_path

    def speech_to_speech(
        self, audio: io.BytesIO | str, source_lang: str, destination_lang: str
    ):
        if isinstance(audio, str):
            with urlopen(audio) as response:
                audio = io.BytesIO(response.read())
                audio.name = "input.mp3"

        transcribed_text = self._transcribe(audio)
        translated_text = self._translate(
            transcribed_text, source_lang, destination_lang
        )
        return self._generate_audio(translated_text)

    def text_to_text(self, input_text: str, source_lang: str, destination_lang: str):
        return self._translate(input_text, source_lang, destination_lang)
