#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/trading-bot}"
CONFIG_PATH="${CONFIG_PATH:-/etc/trading-bot/bot.toml}"
PYTHON_BIN="${PYTHON_BIN:-${APP_DIR}/.venv/bin/python}"

cd "${APP_DIR}"

"${PYTHON_BIN}" -m trading_bot.cli validate-config --config "${CONFIG_PATH}"
"${PYTHON_BIN}" -m trading_bot.cli run-cycle --config "${CONFIG_PATH}" --limit 10 --initial-equity 1000 --min-notional 1
"${PYTHON_BIN}" -m trading_bot.cli build-dashboard --config "${CONFIG_PATH}"
