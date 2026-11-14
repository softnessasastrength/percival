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
