"""Opt-in local Ollama adapter; loopback only, no remote inference.

Network I/O is limited to an explicitly configured loopback Ollama endpoint.
"""
from __future__ import annotations
import ipaddress
import json
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


def validate_local_endpoint(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Ollama endpoint must be a plain loopback HTTP origin")
    try:
        if not ipaddress.ip_address(parsed.hostname or "").is_loopback:
            raise ValueError("Non-loopback inference is not allowed")
    except ValueError as exc:
        raise ValueError("Use a numeric loopback address, such as http://127.0.0.1:11434") from exc
    return url.rstrip("/")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalOllama:
    def __init__(self, origin: str = "http://127.0.0.1:11434"):
        self.origin = validate_local_endpoint(origin)
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def generate(self, model: str, prompt: str, *, timeout: float = 30, max_output_tokens: int = 256) -> dict:
        if not model or not 1 <= max_output_tokens <= 4096 or not 0 < timeout <= 120:
            raise ValueError("Invalid model or execution limits")
        data = self._request("/api/generate", timeout, {
            "model": model, "prompt": prompt, "stream": False, "options": {"num_predict": max_output_tokens}
        })
        return {"response": data.get("response", ""), "model": data.get("model", model), "input_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count"), "source": "local-ollama"}

    def _request(self, path: str, timeout: float, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(self.origin + path, data=data, headers={"Content-Type": "application/json"})
        with self._opener.open(request, timeout=timeout) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise ValueError("Expected an Ollama JSON object")
        return result

    def list_models(self, timeout: float) -> list[str]:
        models = self._request("/api/tags", timeout).get("models")
        if not isinstance(models, list):
            raise ValueError("Invalid Ollama model list")
        names = []
        for entry in models:
            name = (entry.get("model") or entry.get("name")) if isinstance(entry, dict) else None
            if not isinstance(name, str) or not name:
                raise ValueError("Invalid Ollama model entry")
            names.append(name)
        return names

    def show_model(self, model: str, timeout: float) -> dict:
        return self._request("/api/show", timeout, {"model": model + ":local"})

    def chat(self, model: str, messages: list[dict], options: dict, *,
             think: bool | None, timeout: float) -> dict:
        payload = {"model": model + ":local", "messages": messages, "stream": False, "options": options}
        if think is not None:
            payload["think"] = think
        return self._request("/api/chat", timeout, payload)
