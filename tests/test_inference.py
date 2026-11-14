import pytest
from percival.inference import InferencePolicy, Model, NoEligibleModel, choose_model
from percival.ollama import validate_local_endpoint

LOCAL = Model("gpt-oss:20b", "ollama", "local", frozenset({"text"}))
CLOUD = Model("cloud-test", "example", "cloud", frozenset({"text", "vision"}), 1000)


def test_local_first_even_if_cloud_is_available():
    assert choose_model([CLOUD, LOCAL], {"text"}, InferencePolicy()) == LOCAL


def test_cloud_fallback_disabled_by_default():
    with pytest.raises(NoEligibleModel):
        choose_model([CLOUD], {"text"}, InferencePolicy())


def test_cloud_requires_explicit_policy_and_budget():
    with pytest.raises(NoEligibleModel):
        choose_model([CLOUD], {"text"}, InferencePolicy(cloud_fallback_enabled=True, max_cloud_cost_micro=999))
    assert choose_model([CLOUD], {"text"}, InferencePolicy(cloud_fallback_enabled=True, max_cloud_cost_micro=1000)) == CLOUD


def test_sensitive_tasks_never_leave_local_without_policy_change():
    with pytest.raises(NoEligibleModel):
        choose_model([CLOUD], {"text"}, InferencePolicy(cloud_fallback_enabled=True, max_cloud_cost_micro=1000), sensitive=True)


def test_ollama_requires_loopback():
    assert validate_local_endpoint("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    for bad in ("https://127.0.0.1:11434", "http://192.168.1.2:11434", "http://localhost:11434", "http://127.0.0.1:11434/other"):
        with pytest.raises(ValueError):
            validate_local_endpoint(bad)
