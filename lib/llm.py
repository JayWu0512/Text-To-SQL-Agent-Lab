"""OpenAI-compatible request adapter. The caller's key exists only for this request."""

from __future__ import annotations

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

PROVIDERS = {
    "openai": {"name": "OpenAI", "responses_url": "https://api.openai.com/v1/responses", "models_url": "https://api.openai.com/v1/models"},
    "duke": {"name": "Duke AI Gateway", "responses_url": "https://litellm.oit.duke.edu/v1/responses", "models_url": "https://litellm.oit.duke.edu/v1/models"},
}
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _provider(provider: str) -> dict:
    selected = PROVIDERS.get(provider)
    if selected is None:
        raise ValueError("Choose a supported API provider.")
    return selected


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


def _http_error_message(error: HTTPError, provider_name: str) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8"))
        message = payload.get("error", {}).get("message")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        message = None
    if error.code == 401:
        detail = f" {message}" if message else ""
        return f"{provider_name} rejected the API key. Regenerate the key and paste the new value.{detail}"
    if error.code == 403:
        detail = f" {message}" if message else ""
        return f"{provider_name} denied access to this model or project. Load the available models for this key and select one of them.{detail}"
    if error.code == 429:
        return f"{provider_name} rate-limited this key or project. Check its usage limits and try again."
    if message:
        return f"{provider_name} rejected the request: {message}"
    return f"{provider_name} returned an API error. Try again shortly."


def _request(api_key: str, model: str, instructions: str, prompt: str, provider: str = "openai", structured: bool = True) -> str:
    selected = _provider(provider)
    if not api_key.strip():
        raise ValueError(f"Enter a {selected['name']} API key.")
    if not model.strip():
        raise ValueError("Enter a model name.")
    payload = {"model": model, "instructions": instructions, "input": prompt}
    if structured:
        payload["text"] = {"format": {"type": "json_object"}}
    body = json.dumps(payload).encode("utf-8")
    request = Request(selected["responses_url"], data=body,
                      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=35, context=SSL_CONTEXT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise ValueError(_http_error_message(error, selected["name"])) from error
    except (URLError, TimeoutError) as error:
        detail = getattr(error, "reason", error)
        raise ValueError(f"{selected['name']} could not be reached: {detail}") from error
    text = _response_text(payload)
    if not text:
        raise ValueError(f"{selected['name']} returned no usable response.")
    return text


def list_models(api_key: str, provider: str = "openai") -> dict:
    """Return only model IDs the selected key can see; keys are never retained."""
    selected = _provider(provider)
    if not api_key.strip():
        raise ValueError(f"Enter a {selected['name']} API key first.")
    request = Request(selected["models_url"], headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise ValueError(_http_error_message(error, selected["name"])) from error
    except (URLError, TimeoutError) as error:
        detail = getattr(error, "reason", error)
        raise ValueError(f"{selected['name']} could not be reached: {detail}") from error
    models = sorted(
        item["id"] for item in payload.get("data", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("mode") in {"chat", "responses"}
    )
    if not models:
        raise ValueError(f"{selected['name']} returned no available models for this key.")
    return {"models": models}


def test_connection(api_key: str, model: str, provider: str = "openai") -> dict:
    selected = _provider(provider)
    _request(api_key, model, "Reply with OK.", "Reply with OK.", provider, structured=False)
    return {"message": f"Connected to {selected['name']}."}


def generate_json(api_key: str, model: str, prompt: str, provider: str = "openai") -> dict:
    instructions = "You are a PostgreSQL Text-to-SQL assistant. Return JSON only. Never include chain-of-thought."
    raw = _request(api_key, model, instructions, prompt, provider)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("The model did not return valid structured output. Try again.") from error
