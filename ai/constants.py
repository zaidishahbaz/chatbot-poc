TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "update_user_preference",
            "description": "Detect user language and update the preference if language is not english",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Drivers detected language code",
                    }
                },
                "required": ["language"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_route",
            "description": "Get driving route",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Starting point of the journey",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Ending point/destination of the journey",
                    },
                },
                "required": [
                    "origin",
                    "destination",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gas_stations",
            "description": "Get gas stations along the route",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Starting point of the journey",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Ending point/destination of the journey",
                    },
                },
                "required": [
                    "origin",
                    "destination",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]

AI_PROMPT = """
        You are a trucking company dispatcher.
        Your objective is to help truck drivers with their queries.
        Provide truck drivers with
            - Ask drive if they like to change the language on greeting or Detect drivers language and update language
            - User tool function to update language
            - Driving routes and improve efficiency
            - Help with the nearest accommodations details
            - Help with the nearest restaurants
            - Help with any other driver questions

        You should respond in english language regardless of drivers configuration
        Supported languages and language codes are:
            English - en
            Hindi - hi
            French - fr
            Spanish - es
        """
