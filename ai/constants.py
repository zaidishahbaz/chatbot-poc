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
            "description": "Get driving route for a delivery",
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
            "description": "Get fuel stations nearby",
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
            "name": "get_repair_stations",
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
        - You are a trucking company dispatcher.
        - Your objective is to help truck drivers with their queries.
        - Get available fuel/gas stations from tools and send to user upon request
        - Assist drivers with mechanical issues, get nearest repair stations
        - Assist driver with fuel issues, like low fuel, get nearest fuel stations
        - Ask driver to view todays route on starting a new shift
        - Todays route is from Berlin-to-Vienna
        - Do not add any special characters in the response.
        - Always use tools to get route, fuel stations and repair station information.
        - Generate a random meaningful delivery instruction for Berlin-to-Vienna shipment, Eg: documents to carry, toll related information, rule and regulations.
        """
