#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This bootstrap script targets macOS." >&2
  exit 1
fi
command -v python3 >/dev/null || { echo "Install Python 3.11+ first." >&2; exit 1; }
python3 - <<'PY'
import sys
if sys.version_info < (3,11):
    raise SystemExit("Python 3.11+ required")
PY
command -v ollama >/dev/null || { echo "Ollama not found. Install and start Ollama first: https://ollama.com/download" >&2; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install -e .
if ! curl --silent --fail --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "Ollama isn't responding on 127.0.0.1:11434. Start the Ollama app or 'ollama serve'." >&2
  exit 1
fi
mkdir -p .local/bin
cat > .local/bin/percival <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec "$ROOT/.venv/bin/python" -m percival "$@"
SH
chmod +x .local/bin/percival
printf '\nInstalled locally. From this repo run:\n  ./.local/bin/percival chat\nOr add %s/.local/bin to PATH to use: percival chat\n' "$PWD"
