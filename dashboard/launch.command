#!/bin/zsh
cd "$(dirname "$0")/.." || exit 1
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python dashboard/app.py
else
  python3 dashboard/app.py
fi
read '?Press Return to close this window.'
