"""Capability-aware local-first routing. No cloud API calls in M0."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


class NoEligibleModel(Exception):
    pass


@dataclass(frozen=True)
class Model:
    name: str
    provider: str
    location: Literal["local", "cloud"]
    capabilities: frozenset[str]
    estimated_cost_micro: int = 0
    available: bool = True


@dataclass(frozen=True)
class InferencePolicy:
    cloud_fallback_enabled: bool = False
    sensitive_local_only: bool = True
    max_cloud_cost_micro: int = 0


def choose_model(models: list[Model], required: set[str], policy: InferencePolicy, *, sensitive: bool = False) -> Model:
    eligible = [m for m in models if m.available and required <= m.capabilities]
    local = [m for m in eligible if m.location == "local"]
    if local:
        return min(local, key=lambda m: (m.estimated_cost_micro, m.name))
    if sensitive and policy.sensitive_local_only:
        raise NoEligibleModel("Sensitive task has no eligible local model")
    if not policy.cloud_fallback_enabled:
        raise NoEligibleModel("No eligible local model; cloud fallback disabled")
    cloud = [m for m in eligible if m.location == "cloud" and m.estimated_cost_micro <= policy.max_cloud_cost_micro]
    if not cloud:
        raise NoEligibleModel("No eligible cloud model within per-call cost ceiling")
    return min(cloud, key=lambda m: (m.estimated_cost_micro, m.name))
