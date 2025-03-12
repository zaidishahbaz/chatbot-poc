import io
import json
import logging
import math
import os
import urllib.parse
import uuid
from typing import Literal
from urllib.request import urlopen

import requests
from django.conf import settings
from geopy.geocoders import Nominatim
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

    def _detect_language(self, content: str):
        detected_lang = self.translation_client.detect_language(content).get(
            "language", "en"
        )
        if "-" in detected_lang:
            detected_lang = detected_lang.split("-")[0]
        return detected_lang

    def _transcribe(self, audio: io.BytesIO) -> str:
        transcription = self.open_ai_client.audio.transcriptions.create(
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

    SERVICE_OPTION_MAP = {
        "1": "View todays route",
        "2": "Find nearest fuel stations",
        "3": "Find nearest repair stations",
        "4": "Review Delivery Instructions",
    }

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
        try:
            existing_preference = UserPreference.objects.get(user=self.user)
            if existing_preference.language == selected_language.value:
                return None
            existing_preference.language = selected_language.value
            existing_preference.save()
        except UserPreference.DoesNotExist:
            UserPreference.objects.create(
                user=self.user, language=selected_language.value
            )

        self._update_session_history(
            content="Updated user preference",
            role=SessionRole.DEVELOPER,
        )
        return f"Your preferred language is set to {selected_language.name.lower()}"

    def handle_get_route(self, origin: str, destination: str):
        """
        Tool handler function to get route
        """
        route_map = self.generate_google_maps_link(origin, destination)
        recommended_fuel_stop = self.get_gas_stations_on_route("Berlin", "Vienna")[0]
        return f"""Route sent!\n\nPickUp: {origin} (9:00 AM),
            \n\nDelivery: {destination} (5:00 PM)
            \n\n{route_map}
            \n\nRecommended Fuel Stop: {math.ceil(recommended_fuel_stop['distance'])}KMs ({recommended_fuel_stop['name']})
            \n\nRoute: {recommended_fuel_stop['link']}"""

    def handle_get_gas_stations(self, origin: str, destination: str):
        ai_response = ""

        gas_stations = self.get_gas_stations_on_route(origin, destination)
        ai_response = ""
        for station in gas_stations:
            ai_response += (
                f"Name: {station['name']} | {math.ceil(station['distance'])}Kms"
            )
            ai_response += f"\n{station['link']}"
            ai_response += "\n\n"

        self._update_session_history(
            content=f"Gas station found: {gas_stations}, Share the details with user",
            role=SessionRole.DEVELOPER,
        )
        return ai_response

    def handle_get_repair_stations(self, origin: str, destination: str):
        ai_response = ""

        repair_stations = self.get_repair_shops_on_route(origin, destination)
        if repair_stations:
            for station in repair_stations:
                ai_response += (
                    f"Name: {station['name']} | {math.ceil(station['distance'])}Kms"
                )
                ai_response += f"\n{station['link']}"
                ai_response += "\n\n"

        self._update_session_history(
            content=f"Repair shops found: {repair_stations}, Share the details with user",
            role=SessionRole.DEVELOPER,
        )
        return ai_response

    def translate(self, message, direction: Literal["IN"] | Literal["OUT"] = "OUT"):
        """
        Translate to language configure by the user
        """
        try:
            language_preference_config = UserPreference.objects.get(user=self.user)
            language = language_preference_config.language
        except UserPreference.DoesNotExist:
            language = "en"

        if language != "en":
            if direction == "IN":
                source_lang = language
                destination_lang = "en"
            else:
                source_lang = "en"
                destination_lang = language

            message = self.translation_util.text_to_text(
                message,
                source_lang=source_lang,
                destination_lang=destination_lang,
            )
        return message

    def append_service_option_message(self, message: str):
        message += "\n\n"
        for key, value in self.SERVICE_OPTION_MAP.items():
            message += f"{key}. {self.translate(value)}"
            message += "\n"
        return message

    def ai_response(self, message: str = None, media_url: str = None):
        """Generates a trucking response and suggests refueling stations if applicable."""

        message = self.translate(message, "IN")
        # Handle language selection
        self._update_session_history(
            content=message,
            role=SessionRole.USER,
        )

        # Generate ai response
        response = self._get_gpt_response()
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            message = self._process_tool_call(tool_call)
            # Skip voice generation for tool output
            message = self.translate(message)
            return self.append_service_option_message(message), "text"
        else:
            message = response.choices[0].message.content

        message = self.translate(message)

        if media_url:
            return self.translation_util._generate_audio(message), "audio"

        message = self.append_service_option_message(message)
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
        places_url = "https://places.googleapis.com/v1/places:searchNearby"

        # Get midpoint between origin and destination (rough estimate)
        midpoint = (
            origin  # Simplified, ideally get a midpoint via Google Directions API
        )

        geolocator = Nominatim(user_agent="geocoding_app")
        location = geolocator.geocode(midpoint)

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.google_maps_api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.fuelOptions,routingSummaries.legs.distanceMeters",
        }

        payload = {
            "includedTypes": ["gas_station"],
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                    },
                    "radius": 5000,
                }
            },
            "routingParameters": {
                "origin": {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                },
                "routingPreference": "TRAFFIC_AWARE",
            },
        }

        response = requests.post(places_url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            gas_stations = []

            places = data["places"][:3]
            summaries = data["routingSummaries"][:3]
            for i in range(len(places)):
                place = places[i]
                summary = summaries[i]

                name = (
                    place["displayName"]["text"]
                    + " "
                    + place["formattedAddress"].split(" ")[0]
                )
                fuel_station = {
                    "name": name,
                    "distance": summary["legs"][0]["distanceMeters"] / 1000,
                    "link": self.generate_google_maps_link(midpoint, name),
                }

                fuel_options = place.get("fuelOptions")
                if fuel_options:
                    fuel_prices = ", ".join(
                        [
                            f"{item['type']}: {item['price']['nanos']/10000000}€"
                            for item in fuel_options["fuelPrices"]
                        ]
                    )
                    fuel_station["fuel_prices"] = fuel_prices
                gas_stations.append(fuel_station)

            return gas_stations
        return []

    def get_repair_shops_on_route(self, origin: str, destination: str):
        places_url = "https://places.googleapis.com/v1/places:searchNearby"

        # Get midpoint between origin and destination (rough estimate)
        midpoint = (
            origin  # Simplified, ideally get a midpoint via Google Directions API
        )

        geolocator = Nominatim(user_agent="geocoding_app")
        location = geolocator.geocode(midpoint)

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.google_maps_api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.fuelOptions,routingSummaries.legs.distanceMeters",
        }

        payload = {
            "includedTypes": ["car_repair"],
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                    },
                    "radius": 5000,
                }
            },
            "routingParameters": {
                "origin": {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                },
                "routingPreference": "TRAFFIC_AWARE",
            },
        }

        response = requests.post(places_url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            repair_stations = []

            places = data["places"][:3]
            summaries = data["routingSummaries"][:3]
            for i in range(len(places)):
                place = places[i]
                summary = summaries[i]

                name = (
                    place["displayName"]["text"]
                    + " "
                    + place["formattedAddress"].split(" ")[0]
                )
                fuel_station = {
                    "name": name,
                    "distance": summary["legs"][0]["distanceMeters"] / 1000,
                    "link": self.generate_google_maps_link(midpoint, name),
                }
                repair_stations.append(fuel_station)

            return repair_stations

        return []
