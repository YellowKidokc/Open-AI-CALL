#!/usr/bin/env python3
"""
Unified, multi-provider API client.

One function -- call() -- takes a provider name, a model, a key, a prompt and a
list of attachments, and returns a normalized result dict:

    {
      "text":          "<the model's reply>",
      "input_tokens":  <int>,
      "output_tokens": <int>,
      "model":         "<model used>",
      "provider":      "<provider used>",
      "elapsed":       <seconds, float>,
    }

OpenAI / DeepSeek / Kimi all speak the OpenAI chat-completions protocol, so
they share one code path (just a different base_url). Anthropic uses its own
SDK and message shape.

SDKs are imported lazily so you only need the package for the providers you
actually use.
"""

import time
import base64
import mimetypes

import providers as P


# ---------------------------------------------------------------------------
#  Retry helper (the SDKs already retry, but we add explicit backoff so a long
#  unattended batch survives transient rate limits / 5xx outages)
# ---------------------------------------------------------------------------

_RETRYABLE_NAMES = {
    "RateLimitError", "APITimeoutError", "InternalServerError",
    "APIConnectionError", "OverloadedError", "APIStatusError",
}


def _is_retryable(exc: Exception) -> bool:
    name = exc.__class__.__name__
    if name in _RETRYABLE_NAMES:
        status = getattr(exc, "status_code", None)
        if name == "APIStatusError":
            return status is None or status >= 500 or status == 429
        return True
    status = getattr(exc, "status_code", None)
    return status is not None and (status == 429 or status >= 500)


def _with_retry(fn, max_retries: int):
    delay = 2.0
    last = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:               # noqa: BLE001 - we re-raise below
            last = exc
            if attempt >= max_retries or not _is_retryable(exc):
                raise
            print(f"    ! transient error ({exc.__class__.__name__}); "
                  f"retry {attempt + 1}/{max_retries} in {delay:.0f}s")
            time.sleep(delay)
            delay *= 2
    raise last


# ---------------------------------------------------------------------------
#  Attachment helpers
# ---------------------------------------------------------------------------

def _read_text(path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _image_data_url(path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}", mime, b64


# ---------------------------------------------------------------------------
#  OpenAI-compatible providers (openai, deepseek, kimi)
# ---------------------------------------------------------------------------

def _call_openai_compatible(pconf, provider, model, api_key, prompt,
                            attachments, max_tokens, temperature,
                            system, timeout, max_retries):
    try:
        import openai
    except ImportError as e:
        raise RuntimeError(
            "The 'openai' package is required for this provider.\n"
            "Install it with:  pip install openai"
        ) from e

    client = openai.OpenAI(
        api_key=api_key,
        base_url=pconf["base_url"],
        timeout=timeout,
        max_retries=0,            # we handle retries ourselves
    )

    content = [{"type": "text", "text": prompt}]
    for name, path, kind in attachments:
        if kind == "text":
            content.append({"type": "text",
                            "text": f"\n--- FILE: {name} ---\n" + _read_text(path)})
        elif kind == "image" and pconf["vision"]:
            data_url, _, _ = _image_data_url(path)
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        elif kind == "image":
            content.append({"type": "text",
                            "text": f"\n[image '{name}' skipped: {provider} has no vision support]\n"})
        else:
            content.append({"type": "text",
                            "text": f"\n[binary file '{name}' skipped]\n"})

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})

    kwargs = {"model": model, "messages": messages}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    t0 = time.time()
    resp = _with_retry(lambda: client.chat.completions.create(**kwargs), max_retries)
    elapsed = time.time() - t0

    reply = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    return {
        "text": reply,
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "model": model,
        "provider": provider,
        "elapsed": elapsed,
    }


# ---------------------------------------------------------------------------
#  Anthropic (Claude)
# ---------------------------------------------------------------------------

def _call_anthropic(pconf, provider, model, api_key, prompt, attachments,
                    max_tokens, temperature, thinking, system,
                    timeout, max_retries):
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "The 'anthropic' package is required for the Anthropic provider.\n"
            "Install it with:  pip install anthropic"
        ) from e

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)

    blocks = [{"type": "text", "text": prompt}]
    for name, path, kind in attachments:
        if kind == "text":
            blocks.append({"type": "text",
                           "text": f"\n--- FILE: {name} ---\n" + _read_text(path)})
        elif kind == "image":
            _, mime, b64 = _image_data_url(path)
            blocks.append({"type": "image",
                           "source": {"type": "base64", "media_type": mime, "data": b64}})
        else:
            blocks.append({"type": "text", "text": f"\n[binary file '{name}' skipped]\n"})

    kwargs = {
        "model": model,
        "max_tokens": max_tokens or 4096,
        "messages": [{"role": "user", "content": blocks}],
    }
    if system:
        kwargs["system"] = system
    # Adaptive thinking is opt-in for this batch tool (keeps cost/latency down
    # by default). Set THINKING=adaptive in a folder config to turn it on.
    if thinking == "adaptive":
        kwargs["thinking"] = {"type": "adaptive"}

    t0 = time.time()
    resp = _with_retry(lambda: client.messages.create(**kwargs), max_retries)
    elapsed = time.time() - t0

    # Skip thinking blocks; concatenate the text blocks.
    reply = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    usage = getattr(resp, "usage", None)
    return {
        "text": reply,
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "model": model,
        "provider": provider,
        "elapsed": elapsed,
    }


# ---------------------------------------------------------------------------
#  Public entry point
# ---------------------------------------------------------------------------

def call(provider, model, api_key, prompt, attachments,
         max_tokens=4096, temperature=0.7, thinking="off",
         system="", timeout=600.0, max_retries=4):
    """Make one API call and return a normalized result dict."""
    pconf = P.get_provider(provider)
    provider = P.normalize_provider(provider)
    model = model or pconf["default_model"]

    if not api_key:
        raise RuntimeError(
            f"No API key found for provider '{provider}'.\n"
            f"Add one to keys.txt (key name: {pconf['key_names'][0]}) "
            f"or set the environment variable.\n"
            f"Get a key at: {pconf['keys_url']}"
        )

    if pconf["kind"] == "anthropic":
        return _call_anthropic(pconf, provider, model, api_key, prompt, attachments,
                               max_tokens, temperature, thinking, system,
                               timeout, max_retries)
    return _call_openai_compatible(pconf, provider, model, api_key, prompt, attachments,
                                   max_tokens, temperature, system, timeout, max_retries)
