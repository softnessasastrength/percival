"""Opt-in local Ollama adapter; loopback only, no remote inference.

Network I/O is limited to an explicitly configured loopback Ollama endpoint.
"""
from __future__ import annotations
import ipaddress
import json
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


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


class LocalOllama:
    def __init__(self, origin: str = "http://127.0.0.1:11434"):
        self.origin = validate_local_endpoint(origin)

    def generate(self, model: str, prompt: str, *, timeout: float = 30, max_output_tokens: int = 256) -> dict:
        if not model or not 1 <= max_output_tokens <= 4096 or not 0 < timeout <= 120:
            raise ValueError("Invalid model or execution limits")
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": max_output_tokens}}).encode()
        request = Request(self.origin + "/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        return {"response": data.get("response", ""), "model": data.get("model", model), "input_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count"), "source": "local-ollama"}
