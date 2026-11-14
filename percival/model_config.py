"""Load terminal agent profiles and their Ollama model settings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml

DEFAULT_CONFIG = Path(__file__).with_name("models.yaml")
AGENT_CONTRACT = Path(__file__).with_name("AGENTS.md")
REASONING_MODES = ("off", "on", "default")


@dataclass(frozen=True)
class ModelSettings:
    context_tokens: int = 4096
    output_tokens: int = 512


@dataclass(frozen=True)
class AgentProfile:
    instructions: str
    models: tuple[str, ...]
    reasoning: str


@dataclass(frozen=True)
class Registry:
    default_agent: str
    models: dict[str, ModelSettings]
    agents: dict[str, AgentProfile]


def local_tag(value: str) -> str:
    """Normalize a model name as listed by Ollama and reject cloud selectors."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[\w.-]+(?::[0-9]+)?(?:/[\w.-]+)*(?::[\w.-]+)?", value, re.ASCII
    ):
        raise ValueError(f"Invalid Ollama model name: {value!r}")
    name = value.rsplit("/", 1)[-1]
    if name.lower().endswith((":cloud", "-cloud", ":local")):
        raise ValueError(f"Use a plain installed Ollama model tag: {value!r}")
    return value if ":" in name else value + ":latest"


def _mapping(value: object, label: str, fields: set[str] | None = None) -> dict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a mapping with string keys")
    if fields is not None and value.keys() - fields:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(value.keys() - fields))}")
    return value


def load_registry(path: Path = DEFAULT_CONFIG) -> Registry:
    try:
        contract = AGENT_CONTRACT.read_text(encoding="utf-8").strip()
        data = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "config",
                        {"version", "default_agent", "models", "agents"})
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot load agent contract or model config {path}: {exc}") from exc
    if not contract:
        raise ValueError("Agent contract is empty")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Model config version must be 1")

    models = {}
    for tag, raw_settings in _mapping(data.get("models"), "models").items():
        settings = ModelSettings(**_mapping(raw_settings, tag, {"context_tokens", "output_tokens"}))
        if (type(settings.context_tokens) is not int or type(settings.output_tokens) is not int
                or not 0 < settings.output_tokens < settings.context_tokens):
            raise ValueError(f"{tag} needs positive token limits with output below context")
        normalized = local_tag(tag)
        if normalized in models:
            raise ValueError(f"Duplicate model tag: {normalized}")
        models[normalized] = settings

    agents = {}
    for name, raw_profile in _mapping(data.get("agents"), "agents").items():
        profile = _mapping(raw_profile, name, {"instructions", "models", "reasoning"})
        tags = profile.get("models")
        if not isinstance(tags, list) or not tags:
            raise ValueError(f"{name} needs an ordered list of models")
        candidates = tuple(local_tag(tag) for tag in tags)
        if len(set(candidates)) != len(candidates) or set(candidates) - models.keys():
            raise ValueError(f"{name} must list distinct registered model tags")
        reasoning = profile.get("reasoning", "off")
        if reasoning not in REASONING_MODES:
            raise ValueError(f'{name} reasoning must be "off", "on", or "default"')
        instructions = profile.get("instructions")
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError(f"{name} needs an instructions file")
        try:
            prompt = (path.parent / instructions).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"Cannot read instructions for {name}: {exc}") from exc
        if not prompt:
            raise ValueError(f"{name} instructions are empty")
        agents[name] = AgentProfile(f"{contract}\n\n## Selected profile\n\n{prompt}", candidates, reasoning)

    default = data.get("default_agent")
    if not isinstance(default, str) or default not in agents:
        raise ValueError("default_agent must name a configured agent")
    return Registry(default, models, agents)
