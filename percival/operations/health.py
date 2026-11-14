"""Read-only, allowlisted operations probes. No discovery or remediation."""
from __future__ import annotations
import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from ..ollama import validate_local_endpoint


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    timestamp: float


def probe_ollama(origin: str = "http://127.0.0.1:11434", timeout: float = 3) -> Check:
    origin = validate_local_endpoint(origin)
    try:
        with urlopen(Request(origin + "/api/tags", method="GET"), timeout=timeout) as response:
            payload = json.load(response)
        models = [str(item.get("name", "")) for item in payload.get("models", [])]
        return Check("ollama", "healthy", "Installed models: " + (", ".join(models) or "none"), time.time())
    except (URLError, HTTPError, TimeoutError, ValueError, KeyError, OSError) as exc:
        return Check("ollama", "unavailable", type(exc).__name__, time.time())


def disk_check(path: str = "/", min_free_gib: float = 5.0) -> Check:
    free = shutil.disk_usage(path).free / (1024 ** 3)
    return Check("disk", "healthy" if free >= min_free_gib else "warning", f"{free:.1f} GiB free", time.time())


def approved_endpoint_check(name: str, url: str, *, timeout: float = 3) -> Check:
    # Explicitly supplied URL only. This routine does not discover the network.
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Approved endpoints must be HTTPS URLs without embedded credentials or fragments")
    try:
        with urlopen(Request(url, method="HEAD"), timeout=timeout) as response:
            status = response.status
        return Check(name, "healthy" if status < 400 else "warning", f"HTTP {status}", time.time())
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        return Check(name, "unavailable", type(exc).__name__, time.time())


def report(*, origin: str = "http://127.0.0.1:11434", disk_path: str = "/") -> list[Check]:
    return [probe_ollama(origin), disk_check(disk_path)]


def render_json(checks: list[Check]) -> str:
    return json.dumps([asdict(item) for item in checks], indent=2)
