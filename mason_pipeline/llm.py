from typing import Dict, List

from ollama import Client

_ollama = Client()


def chat(model: str, messages: List[Dict[str, str]]) -> str:
    """Send a chat request to Ollama and return the response content string."""
    return _ollama.chat(model, messages=messages)["message"]["content"]
