"""Configuration helpers for Agent API settings."""
import json
import os
from pathlib import Path
from typing import Any, Dict


def load_claude_code_env() -> Dict[str, str]:
    """Load Claude Code API-related env values from ~/.claude.json."""
    config_path = Path.home() / ".claude.json"
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    env = data.get("env", {})
    if not isinstance(env, dict):
        return {}

    return {str(key): str(value) for key, value in env.items() if value is not None}


def load_agent_config(config_path: Any) -> Dict[str, Any]:
    """Load agent_config.json and overlay Claude Code compatible API settings."""
    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

    api_config = config.setdefault("api", {})
    claude_env = load_claude_code_env()

    base_url = (
        os.getenv("ANTHROPIC_BASE_URL")
        or claude_env.get("ANTHROPIC_BASE_URL")
        or os.getenv("CLAUDE_API_BASE_URL")
    )
    api_key = (
        os.getenv("ANTHROPIC_AUTH_TOKEN")
        or claude_env.get("ANTHROPIC_AUTH_TOKEN")
        or os.getenv("ANTHROPIC_API_KEY")
        or claude_env.get("ANTHROPIC_API_KEY")
        or os.getenv("CLAUDE_API_KEY")
    )
    model = (
        os.getenv("ANTHROPIC_MODEL")
        or claude_env.get("ANTHROPIC_MODEL")
        or os.getenv("CLAUDE_MODEL")
    )
    timeout_ms = os.getenv("API_TIMEOUT_MS") or claude_env.get("API_TIMEOUT_MS")

    if base_url:
        api_config["base_url"] = base_url
    if api_key:
        api_config["api_key"] = api_key
    if model:
        api_config["model"] = model
    if timeout_ms:
        try:
            api_config["timeout"] = max(1, int(timeout_ms) // 1000)
        except ValueError:
            pass

    return config
