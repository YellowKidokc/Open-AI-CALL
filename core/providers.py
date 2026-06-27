#!/usr/bin/env python3
"""
Provider registry + API-key resolution for the multi-API batch processor.

Four providers are supported out of the box:

    openai      - OpenAI (GPT-4o, etc.)            -> uses the `openai` SDK
    anthropic   - Anthropic (Claude)               -> uses the `anthropic` SDK
    deepseek    - DeepSeek (OpenAI-compatible API) -> uses the `openai` SDK + base_url
    kimi        - Moonshot / Kimi K2 (OpenAI-compat)-> uses the `openai` SDK + base_url

To add a new provider, add an entry to PROVIDERS below. If it speaks the
OpenAI chat-completions protocol, set "kind": "openai" and give it a base_url.
"""

import os
import pathlib

# Repo root = the folder that contains core/  (one level up from this file)
ROOT = pathlib.Path(__file__).resolve().parent.parent
KEYS_FILE = ROOT / "keys.txt"

# ---------------------------------------------------------------------------
#  Provider table
# ---------------------------------------------------------------------------
#  pricing values are (input $/1K tokens, output $/1K tokens) and are only
#  used for the cost ESTIMATE printed after each call. They drift over time --
#  update them when you like; a missing entry just means "cost not estimated".
# ---------------------------------------------------------------------------
PROVIDERS = {
    "openai": {
        "kind": "openai",
        "base_url": None,                       # default OpenAI endpoint
        "default_model": "gpt-4o",
        "key_names": ["OPENAI_API_KEY"],
        "vision": True,
        "pricing": {
            "gpt-4o":       (0.0025,  0.0100),
            "gpt-4o-mini":  (0.00015, 0.0006),
            "gpt-4-turbo":  (0.0100,  0.0300),
            "o3-mini":      (0.0011,  0.0044),
        },
        "keys_url": "https://platform.openai.com/api-keys",
    },
    "anthropic": {
        "kind": "anthropic",
        "base_url": None,
        "default_model": "claude-opus-4-8",
        "key_names": ["ANTHROPIC_API_KEY"],
        "vision": True,
        "pricing": {
            "claude-opus-4-8":   (0.0050, 0.0250),
            "claude-opus-4-7":   (0.0050, 0.0250),
            "claude-sonnet-4-6": (0.0030, 0.0150),
            "claude-haiku-4-5":  (0.0010, 0.0050),
        },
        "keys_url": "https://console.anthropic.com/settings/keys",
    },
    "deepseek": {
        "kind": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "key_names": ["DEEPSEEK_API_KEY"],
        "vision": False,
        "pricing": {  # approximate, cache-miss pricing
            "deepseek-chat":     (0.00027, 0.0011),
            "deepseek-reasoner": (0.00055, 0.00219),
        },
        "keys_url": "https://platform.deepseek.com/api_keys",
    },
    "kimi": {
        "kind": "openai",
        # International endpoint. For the China endpoint use:
        #   https://api.moonshot.cn/v1
        "base_url": "https://api.moonshot.ai/v1",
        "default_model": "kimi-k2-0905-preview",
        "key_names": ["KIMI_API_KEY", "MOONSHOT_API_KEY"],
        "vision": False,
        "pricing": {},   # varies by model / region -- left blank
        "keys_url": "https://platform.moonshot.ai/console/api-keys",
    },
}

# Friendly aliases the user might type in a config file.
ALIASES = {
    "moonshot": "kimi",
    "kimmy":    "kimi",
    "kimi-k2":  "kimi",
    "claude":   "anthropic",
    "anthropics": "anthropic",
    "gpt":      "openai",
    "oai":      "openai",
    "chatgpt":  "openai",
    "deep-seek": "deepseek",
    "deepsea":  "deepseek",
}


def normalize_provider(name: str) -> str:
    """Lower-case + de-alias a provider name."""
    key = (name or "").strip().lower()
    return ALIASES.get(key, key)


def get_provider(name: str) -> dict:
    """Return the provider config dict, raising a clear error if unknown."""
    key = normalize_provider(name)
    if key not in PROVIDERS:
        known = ", ".join(sorted(PROVIDERS))
        raise ValueError(
            f"Unknown provider '{name}'. Known providers: {known}.\n"
            f"(Check the PROVIDER= line in your folder's config.txt.)"
        )
    return PROVIDERS[key]


# ---------------------------------------------------------------------------
#  Key resolution
# ---------------------------------------------------------------------------

def load_keys_file() -> dict:
    """Read KEY=VALUE pairs from the root keys.txt (if it exists)."""
    keys = {}
    if KEYS_FILE.exists():
        for line in KEYS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            keys[k.strip().upper()] = v.strip()
    return keys


def resolve_key(provider: str, explicit: str = "") -> str:
    """
    Find an API key for a provider, in priority order:
        1. an explicit key passed in (e.g. API_KEY= in the folder config)
        2. the matching entry in the root keys.txt
        3. an environment variable of the same name
    Returns "" if nothing is found.
    """
    explicit = (explicit or "").strip()
    if explicit and not explicit.upper().startswith(("PASTE", "SK-PASTE", "YOUR")):
        return explicit

    pconf = get_provider(provider)
    file_keys = load_keys_file()
    for name in pconf["key_names"]:
        if file_keys.get(name.upper()):
            return file_keys[name.upper()]
        if os.environ.get(name):
            return os.environ[name]
    return ""


def price_for(provider: str, model: str):
    """Return (in_rate, out_rate) per 1K tokens, or None if unknown."""
    pconf = get_provider(provider)
    return pconf["pricing"].get(model)
