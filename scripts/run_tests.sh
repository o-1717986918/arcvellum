#!/usr/bin/env bash
set -euo pipefail

repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$repository/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  python_bin="${PYTHON:-python3}"
fi
export PYTHONPATH="$repository/src${PYTHONPATH:+:$PYTHONPATH}"

"$python_bin" "$repository/scripts/verify_checkout_import.py"
"$python_bin" -m unittest discover -s "$repository/tests" "$@"
