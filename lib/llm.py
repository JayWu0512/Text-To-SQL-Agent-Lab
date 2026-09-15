"""OpenAI request adapter. The caller's key exists only for this request."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _response_text(payload: dict) -> str:
    """Extract text from a raw Responses API response.

    ``output_text`` is an SDK convenience property; REST responses carry text
    inside message content items.
    """
    direct_text = payload.get("output_text")
    if isinstance(direct_text, str) and direct_text:
        return direct_text
    texts = []
    for output in payload.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    texts.append(text)
    return "".join(texts)


def _http_error_message(error: HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8"))
        message = payload.get("error", {}).get("message")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        message = None
    if error.code in {401, 403}:
        return "OpenAI rejected the API key or this project does not have access to the selected model."
    if error.code == 429:
        return "OpenAI rate-limited this key or project. Check its usage limits and try again."
    if message:
        return f"OpenAI rejected the request: {message}"
    return "OpenAI returned an API error. Try again shortly."


def _request(api_key: str, model: str, instructions: str, prompt: str) -> str:
    if not api_key.startswith("sk-"):
        raise ValueError("Enter a valid OpenAI API key.")
    body = json.dumps({"model": model, "instructions": instructions, "input": prompt,
                       "text": {"format": {"type": "json_object"}}}).encode("utf-8")
    request = Request("https://api.openai.com/v1/responses", data=body,
                      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise ValueError(_http_error_message(error)) from error
    except (URLError, TimeoutError) as error:
        raise ValueError("OpenAI could not be reached. Check your network and try again.") from error
    text = _response_text(payload)
    if not text:
        raise ValueError("OpenAI returned no usable response.")
    return text


def test_connection(api_key: str, model: str) -> dict:
    _request(api_key, model, "Return a JSON object with one field named ok.", "Return a JSON object: {\"ok\": true}.")
    return {"message": "Connected to OpenAI."}


def generate_json(api_key: str, model: str, prompt: str) -> dict:
    instructions = "You are a PostgreSQL Text-to-SQL assistant. Return JSON only. Never include chain-of-thought."
    raw = _request(api_key, model, instructions, prompt)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("The model did not return valid structured output. Try again.") from error
