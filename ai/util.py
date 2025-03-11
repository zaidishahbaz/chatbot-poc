import io
import logging
import os
import urllib.parse
import uuid
from urllib.request import urlopen

import requests
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
        self.google_maps_api_key = settings.GOOGLE_MAPS_API_KEY
        self.fuel_origin = None
        self.fuel_destination = None

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

    def ai_response(self, message: str) -> str:
        """Generates a trucking response and suggests refueling stations if applicable."""

        prompt = f"""
        You are a trucking company dispatcher. If the user asks for a route, extract the origin and destination
        and generate a Google Maps link. Also, suggest gas stations along the way if possible.
        consider you are a 10 tyre truck, and source and destination are {self.fuel_origin} and {self.fuel_destination}

        Question: {message}

        Answer:
        """

        response = self.open_ai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a trucking dispatcher providing guidance to drivers.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.7,
        )

        ai_response = response.choices[0].message.content.strip()

        # Extract locations from user input
        origin, destination = self.extract_locations(message)

        if origin and destination:
            self.fuel_origin = origin
            self.fuel_destination = destination
            # Generate Google Maps Route Link
            maps_link = self.generate_google_maps_link(origin, destination)
            ai_response += (
                f"\n\n🔗 Click here to view the route on Google Maps: {maps_link}"
            )

            # Fetch gas stations along the route
            gas_stations = self.get_gas_stations_on_route(origin, destination)
            if gas_stations:
                ai_response += "\n\n⛽ Suggested Gas Stations Along the Route:\n"
                for station in gas_stations:
                    ai_response += f"- {station['name']} ([View on Google Maps]({station['maps_url']}))\n"

        return ai_response

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
