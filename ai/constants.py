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
    {
        "type": "function",
        "function": {
            "name": "handle_get_repair_stations",
            "description": "Get repair shops along the route",
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

        Detect user language and update user preference on first message
        These are the services we provide, once preference is updated provide these options to user
        and ask them select a service.
            1. View Route
            2. Find Fuel/Service Stations
            3. Change language

        Option 1 :-  Get route information from Berlin-to-Vienna
        Option 2 :- Get gas stations along the way
        Option 3 :- Ask user to select language and update user preference

        You should respond in english language regardless of drivers configuration
        Supported languages and language codes are:
            English - en
            Hindi - hi
            French - fr
            Spanish - es

        Assist drivers with mechanical issues and solutions, and suggest a repair shop along the way.
        """
