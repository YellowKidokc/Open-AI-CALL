#!/usr/bin/env python3
"""
Provider Registry
=================
One place that knows about every AI service this system can call:
its API style, where to send requests, which models it offers, what
they cost, and money-saving tips.

Add a new provider by adding one entry to PROVIDERS below — nothing
else in the system needs to change.

Two API styles are supported:
  * "openai"     — anything that speaks the OpenAI Chat Completions API.
                   That covers OpenAI itself plus DeepSeek, Moonshot/Kimi,
                   Google Gemini (via its OpenAI-compatible endpoint), and
                   xAI Grok. They only differ by base_url + API key.
  * "anthropic"  — Claude, which uses Anthropic's own Messages API.

PRICES ARE APPROXIMATE and stored as (input_$_per_1K, output_$_per_1K).
Provider pricing changes often — treat the dry-run cost as a ballpark and
confirm against each provider's pricing page before a big run.
"""

# ---------------------------------------------------------------------------
#  Provider table
# ---------------------------------------------------------------------------
#  key_var   : the name to look for in config.txt / environment for the API key
#  api       : "openai" or "anthropic"  (how we talk to it)
#  base_url  : override endpoint for OpenAI-compatible services (None = OpenAI's own)
#  vision    : True if the default model accepts images
#  models    : { model_name: (input_$/1K, output_$/1K) }
#  tips      : money / logistics tips printed in the dry-run
# ---------------------------------------------------------------------------

PROVIDERS = {
    # ----------------------------------------------------------------- OpenAI
    "openai": {
        "label": "OpenAI",
        "key_var": "OPENAI_API_KEY",
        "api": "openai",
        "base_url": None,
        "vision": True,
        "default_model": "gpt-4o",
        "models": {
            "gpt-4o":        (0.0025,  0.0100),
            "gpt-4o-mini":   (0.00015, 0.0006),
            "gpt-4.1":       (0.0020,  0.0080),
            "gpt-4.1-mini":  (0.0004,  0.0016),
            "o3-mini":       (0.0011,  0.0044),
        },
        "tips": [
            "Batch API cuts cost ~50% if you can wait up to 24h for results.",
            "gpt-4o-mini is ~15x cheaper than gpt-4o — great for first drafts.",
        ],
    },

    # -------------------------------------------------------------- Anthropic
    "anthropic": {
        "label": "Anthropic (Claude)",
        "key_var": "ANTHROPIC_API_KEY",
        "api": "anthropic",
        "base_url": None,
        "vision": True,
        "default_model": "claude-opus-4-8",
        "models": {
            # $/1K = ($/1M) / 1000
            "claude-opus-4-8":   (0.0050, 0.0250),
            "claude-sonnet-4-6": (0.0030, 0.0150),
            "claude-haiku-4-5":  (0.0010, 0.0050),
            "claude-fable-5":    (0.0100, 0.0500),
        },
        "tips": [
            "Batch API cuts cost ~50% for non-urgent work.",
            "Prompt caching can save up to ~90% on repeated context.",
            "claude-haiku-4-5 is the cheapest Claude for simple/bulk tasks.",
        ],
    },

    # --------------------------------------------------------------- DeepSeek
    "deepseek": {
        "label": "DeepSeek",
        "key_var": "DEEPSEEK_API_KEY",
        "api": "openai",
        "base_url": "https://api.deepseek.com",
        "vision": False,
        "default_model": "deepseek-chat",
        "models": {
            "deepseek-chat":     (0.00027, 0.0011),
            "deepseek-reasoner": (0.00055, 0.00219),
        },
        "tips": [
            "Off-peak discount window (roughly 16:30-00:30 UTC) can be 50-75% cheaper.",
            "Context caching lowers the input cost on repeated prompts.",
            "If geo-blocked, a SOCKS proxy can be set via the ALL_PROXY env var.",
        ],
    },

    # -------------------------------------------------------- Moonshot / Kimi
    "moonshot": {
        "label": "Moonshot (Kimi)",
        "key_var": "MOONSHOT_API_KEY",
        "api": "openai",
        "base_url": "https://api.moonshot.ai/v1",   # use .cn endpoint inside China
        "vision": False,
        "default_model": "kimi-k2-0711-preview",
        "models": {
            "kimi-k2-0711-preview": (0.0006, 0.0025),
            "moonshot-v1-32k":      (0.0012, 0.0012),
            "moonshot-v1-128k":     (0.0060, 0.0060),
        },
        "tips": [
            "Context caching is available and cheap for long, repeated documents.",
            "Use the api.moonshot.cn base_url if you are inside mainland China.",
        ],
    },

    # ----------------------------------------------------------------- Gemini
    "gemini": {
        "label": "Google Gemini",
        "key_var": "GEMINI_API_KEY",
        "api": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "vision": True,
        "default_model": "gemini-2.0-flash",
        "models": {
            "gemini-2.0-flash": (0.0001,  0.0004),
            "gemini-1.5-pro":   (0.00125, 0.0050),
        },
        "tips": [
            "gemini-2.0-flash is one of the cheapest capable models available.",
            "Batch mode cuts cost ~50% for non-urgent jobs.",
        ],
    },

    # ------------------------------------------------------------------- xAI
    "xai": {
        "label": "xAI (Grok)",
        "key_var": "XAI_API_KEY",
        "api": "openai",
        "base_url": "https://api.x.ai/v1",
        "vision": True,
        "default_model": "grok-2-latest",
        "models": {
            "grok-2-latest": (0.0020, 0.0100),
            "grok-beta":     (0.0050, 0.0150),
        },
        "tips": [
            "Grok pricing is flat — no batch discount, so use it when you need it.",
        ],
    },
}

# Order providers are offered / run in by default.
PROVIDER_ORDER = ["openai", "anthropic", "deepseek", "moonshot", "gemini", "xai"]

# General tips that apply no matter which provider you pick.
GENERAL_TIPS = [
    "Run a DRY RUN first — it shows the cost on every provider so you can pick.",
    "Most providers halve the price if you submit through their Batch API and "
    "wait up to 24 hours instead of asking for an instant answer.",
    "Set a SOCKS/HTTP proxy with the ALL_PROXY or HTTPS_PROXY environment "
    "variable if a provider is blocked on your network.",
]


def price_for(provider_id: str, model: str):
    """Return (input_$/1K, output_$/1K) for a model, or None if unknown."""
    prov = PROVIDERS.get(provider_id)
    if not prov:
        return None
    return prov["models"].get(model)


def resolve_model(provider_id: str, cfg: dict) -> str:
    """Pick the model for a provider: config override (e.g. OPENAI_MODEL=) or default."""
    prov = PROVIDERS[provider_id]
    override = cfg.get(f"{provider_id.upper()}_MODEL")
    return override or prov["default_model"]
