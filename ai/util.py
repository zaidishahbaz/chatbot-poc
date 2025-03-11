import io
import json
import logging
import os
import urllib.parse
import uuid
from urllib.request import urlopen

import requests
from django.conf import settings
from google.cloud.translate_v2 import Client
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageToolCall

from ai.constants import AI_PROMPT, TOOLS
from ai.models import Languages, OpenAiConvSession, SessionRole, UserPreference

logger = logging.getLogger(__name__)


class TranslationTranscriptionUtil:
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


class ConversationUtil:
    open_ai_client: OpenAI
    message_history = []

    def __init_session(self, user: str):
        self.messages = [{"role": SessionRole.DEVELOPER.value, "content": AI_PROMPT}]
        session_details = OpenAiConvSession.objects.filter(user=self.user).order_by(
            "created_date"
        )
        for session in session_details.iterator():
            self.messages.append({"role": session.role, "content": session.message})

    def __init__(self, user: str):
        self.open_ai_client = OpenAI(api_key=settings.OPEN_AI_KEY)
        self.google_maps_api_key = settings.GOOGLE_MAPS_API_KEY
        self.fuel_origin = None
        self.fuel_destination = None
        self.user = user
        self.__init_session(user)
        self.translation_util = TranslationTranscriptionUtil()

    def _process_tool_call(self, tool_call: ChatCompletionMessageToolCall):
        """
        Call corresponding handler function for tool calls
        """

        function_name = tool_call.function.name
        handler = getattr(self, f"handle_{function_name}")

        if not handler:
            logger.error(
                "Tool call not defined, returning generic message",
                extra={"tool_call": tool_call, "client": self.gpt_client.pk},
            )

        return handler(**json.loads(tool_call.function.arguments))

    def _update_session_history(
        self,
        content: str | None,
        role: SessionRole,
    ):
        """
        Update session history
        """
        if not content:
            return

        OpenAiConvSession.objects.create(
            user=self.user, message=content, role=role.value
        )

        self.messages.append({"role": role.value, "content": content})

    def _get_gpt_response(self):
        """
        Get ai response based on the chat history
        """

        return self.open_ai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=self.messages,
            max_tokens=200,
            tools=TOOLS,
        )

    def handle_update_user_preference(self, language: str):
        """
        Tool handler function to change language
        """
        selected_language = Languages(language)
        UserPreference.objects.update_or_create(
            user=self.user,
            defaults={"language": selected_language.value},
        )
        self._update_session_history(
            content="Updated user preference",
            role=SessionRole.DEVELOPER,
        )
        return f"✅ Your preferred language has been set to {selected_language.name}."

    def handle_get_route(self, origin: str, destination: str):
        """
        Tool handler function to get route
        """

        self.fuel_origin = origin
        self.fuel_destination = destination
        # Generate Google Maps Route Link
        maps_link = self.generate_google_maps_link(origin, destination)
        ai_response = f"\n\n🔗 Click here to view the route on Google Maps: {maps_link}"

        # Fetch gas stations along the route
        gas_stations = self.get_gas_stations_on_route(origin, destination)
        if gas_stations:
            ai_response += "\n\n⛽ Suggested Gas Stations Along the Route:\n"
            for station in gas_stations:
                ai_response += f"- {station['name']} ([View on Google Maps]({station['maps_url']}))\n"

        self._update_session_history(
            content="Route has been calculated and send to user.",
            role=SessionRole.DEVELOPER,
        )
        return ai_response

    def ai_response(self, message: str = None, media_url: str = None):
        """Generates a trucking response and suggests refueling stations if applicable."""

        # Transcribe audio message
        if media_url:
            with urlopen(media_url) as response:
                audio = io.BytesIO(response.read())
                audio.name = "input.mp3"

            message = self.translation_util._transcribe(audio)

        # Handle language selection
        if "change_lang" in message:
            parts = message.split(" ")
            message = self.handle_update_user_preference(parts[1])
        else:
            self._update_session_history(
                content=message,
                role=SessionRole.USER,
            )

            def translate(message):
                """
                Translate to language configure by the user
                """
                try:
                    language_preference_config = UserPreference.objects.get(
                        user=self.user
                    )
                    language = language_preference_config.language
                except UserPreference.DoesNotExist:
                    language = "en"

                if language != "en":
                    message = self.translation_util.text_to_text(
                        message, source_lang="en", destination_lang=language
                    )
                return message

            # Generate ai response
            response = self._get_gpt_response()
            if response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                message = self._process_tool_call(tool_call)
                # Skip voice generation for tool output
                return translate(message), "text"
            else:
                message = response.choices[0].message.content

            message = translate(message)

            if media_url:
                return self.translation_util._generate_audio(message), "audio"

            return message, "text"

    def extract_locations(self, message: str):
        """Extracts origin and destination from the user's message using a basic pattern."""
        import re

        match = re.search(r"from ([\w\s]+) to ([\w\s]+)", message, re.IGNORECASE)
        if match:
            origin, destination = match.groups()
            return origin.strip(), destination.strip()

        return None, None

    def generate_google_maps_link(self, origin: str, destination: str) -> str:
        """Generates a Google Maps route link between two locations."""
        base_url = "https://www.google.com/maps/dir/"
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        return f"{base_url}{origin_encoded}/{destination_encoded}/"

    def get_gas_stations_on_route(self, origin: str, destination: str):
        """Fetches gas stations along the route using the Google Places API."""
        places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

        # Get midpoint between origin and destination (rough estimate)
        midpoint = (
            destination  # Simplified, ideally get a midpoint via Google Directions API
        )

        params = {
            "location": midpoint,  # Searching near the destination (can be adjusted for midpoint)
            "radius": 5000,  # 5 km radius
            "type": "gas_station",
            "key": self.google_maps_api_key,
        }

        response = requests.get(places_url, params=params)
        if response.status_code == 200:
            data = response.json()
            gas_stations = []

            for place in data.get("results", [])[:3]:  # Limit to 3 stations
                name = place["name"]
                place_id = place["place_id"]
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                gas_stations.append({"name": name, "maps_url": maps_url})

            return gas_stations
        return []
