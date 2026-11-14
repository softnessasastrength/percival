from pathlib import Path

import pytest

from percival.model_config import DEFAULT_CONFIG, load_registry, local_tag


def test_default_registry():
    registry = load_registry()
    profile = registry.agents[registry.default_agent]
    assert profile.models == ("qwen3:4b", "llama3.2:3b")
    assert profile.reasoning == "off"
    assert "British personal operations steward" in " ".join(profile.instructions.split())


@pytest.mark.parametrize(("before", "after", "error"), [
    ('reasoning: "off"', "reasoning: off", "reasoning must be"),
    ("output_tokens: 2048", "output_tokens: 8192", "positive token limits"),
    ('["qwen3:4b", "llama3.2:3b"]', '["unknown:latest"]', "registered model tags"),
    ("default_agent: percival", "default_agent: missing", "default_agent must name"),
])
def test_invalid_registry(tmp_path: Path, before, after, error):
    config = tmp_path / "models.yaml"
    config.write_text(DEFAULT_CONFIG.read_text().replace(before, after))
    (tmp_path / "agents").symlink_to(DEFAULT_CONFIG.parent / "agents", target_is_directory=True)
    with pytest.raises(ValueError, match=error):
        load_registry(config)


@pytest.mark.parametrize("tag", ["model:cloud", "model:4b-cloud", "model:4b:cloud"])
def test_reject_cloud_selectors(tag):
    with pytest.raises(ValueError):
        local_tag(tag)


def test_every_profile_receives_repository_contract():
    contract = (Path(__file__).resolve().parents[1] / "AGENTS.md").read_text().strip()
    for profile in load_registry().agents.values():
        assert profile.instructions.startswith(contract + "\n\n## Selected profile\n\n")
