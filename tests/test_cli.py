from percival.cli import main
from percival.ollama import validate_local_endpoint


def test_cli_help(capsys):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "chat" in capsys.readouterr().out


def test_loopback_origin():
    assert validate_local_endpoint("http://127.0.0.1:11434") == "http://127.0.0.1:11434"


def test_chat_falls_back_without_retaining_reasoning(monkeypatch, capsys):
    from percival.ollama import LocalOllama

    turns = iter(["Good morning.", "Again.", "/reset", "New chat.", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(turns))
    monkeypatch.setattr(LocalOllama, "list_models",
                        lambda self, timeout: ["llama3.2:3b", "qwen3:4b"])
    calls = []

    def request(self, path, timeout, payload=None):
        tag = payload["model"]
        if path == "/api/show":
            return {"thinking": {"values": [True]}} if tag.startswith("qwen3") else {
                "capabilities": ["completion"]
            }
        calls.append(payload)
        if tag.startswith("qwen3"):
            return {"done_reason": "length", "message": {"content": "unmarked draft"}}
        return {"done_reason": "stop", "message": {
            "thinking": "private trace", "content": "<THINK>inline trace</THINK>Good morning."
        }}

    monkeypatch.setattr(LocalOllama, "_request", request)
    assert main(["chat"]) == 0
    assert [call["model"] for call in calls[:2]] == ["qwen3:4b:local", "llama3.2:3b:local"]
    assert calls[0]["think"] is True
    assert "think" not in calls[1]
    assert calls[0]["options"] == {"num_ctx": 4096, "num_predict": 2048}
    assert calls[0]["messages"] == calls[1]["messages"]
    assert [msg["content"] for msg in calls[2]["messages"][1:]] == [
        "Good morning.", "Good morning.", "Again."
    ]
    assert len(calls[4]["messages"]) == 2
    output = capsys.readouterr()
    assert "Percival (llama3.2:3b): Good morning." in output.out
    assert "output limit reached" in output.err
    for trace in ("private trace", "inline trace", "unmarked draft"):
        assert trace not in output.out + output.err


def test_missing_primary_uses_installed_fallback(monkeypatch, capsys):
    from percival.ollama import LocalOllama

    monkeypatch.setattr("builtins.input", lambda prompt: "/exit")
    monkeypatch.setattr(LocalOllama, "list_models", lambda self, timeout: ["llama3.2:3b"])
    assert main(["chat"]) == 0
    assert "Model: llama3.2:3b" in capsys.readouterr().out
    assert main(["chat", "--model", "qwen3:4b"]) == 1
    assert "qwen3:4b" in capsys.readouterr().err


def test_discover_models(monkeypatch, capsys):
    from percival.ollama import LocalOllama

    def request(self, path, timeout, payload=None):
        assert path == "/api/tags"
        assert payload is None
        return {"models": [{"model": "qwen3:4b"}, {"name": "llama3.2"}, {"name": "test:cloud"}]}

    monkeypatch.setattr(LocalOllama, "_request", request)
    assert main(["models"]) == 0
    assert capsys.readouterr().out.splitlines() == ["llama3.2:latest", "qwen3:4b"]


def test_remote_alias_cannot_receive_prompt(monkeypatch, capsys):
    from percival.ollama import LocalOllama

    turns = iter(["Hello", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(turns))
    monkeypatch.setattr(LocalOllama, "list_models", lambda self, timeout: ["alias:latest"])

    def request(self, path, timeout, payload=None):
        assert path == "/api/show"
        return {"remote_host": "https://example.com", "remote_model": "example"}

    monkeypatch.setattr(LocalOllama, "_request", request)
    assert main(["chat", "--model", "alias"]) == 0
    assert "identifies this model as remote" in capsys.readouterr().err


def test_profile_and_reasoning_override(monkeypatch, capsys):
    from percival.ollama import LocalOllama

    turns = iter(["Help me with Python", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(turns))
    monkeypatch.setattr(LocalOllama, "list_models", lambda self, timeout: ["qwen3:4b"])

    def request(self, path, timeout, payload=None):
        if path == "/api/show":
            return {"thinking": {"values": [True, False]}}
        assert payload["think"] is False
        assert "coding specialist" in payload["messages"][0]["content"]
        return {"message": {"content": "What are you writing?"}}

    monkeypatch.setattr(LocalOllama, "_request", request)
    assert main(["chat", "--agent", "coding", "--reasoning", "off"]) == 0
    assert "What are you writing?" in capsys.readouterr().out


def test_connection_failure_during_discovery(monkeypatch, capsys):
    from percival.ollama import LocalOllama

    def unavailable(self, timeout):
        raise ConnectionRefusedError("Ollama is unavailable")

    monkeypatch.setattr(LocalOllama, "list_models", unavailable)
    assert main(["chat"]) == 1
    assert "Ollama is unavailable" in capsys.readouterr().err
