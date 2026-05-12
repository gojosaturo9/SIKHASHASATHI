import os
from pathlib import Path
import re
import tomllib

import streamlit as st


_LOCAL_SECRETS_CACHE = None


# Use: Internal helper for local secrets.
# Linked with: get_secret
def _local_secrets():
    global _LOCAL_SECRETS_CACHE
    if _LOCAL_SECRETS_CACHE is not None:
        return _LOCAL_SECRETS_CACHE

    secrets_path = Path(__file__).resolve().parents[2] / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        _LOCAL_SECRETS_CACHE = {}
        return _LOCAL_SECRETS_CACHE

    try:
        with secrets_path.open("rb") as handle:
            _LOCAL_SECRETS_CACHE = tomllib.load(handle)
    except Exception:
        parsed = {}
        try:
            for line in secrets_path.read_text(encoding="utf-8-sig").splitlines():
                match = re.match(
                    r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']?(.*?)["\']?\s*$',
                    line,
                )
                if match:
                    parsed[match.group(1)] = match.group(2).strip()
        except Exception:
            parsed = {}
        _LOCAL_SECRETS_CACHE = parsed
    return _LOCAL_SECRETS_CACHE


# Use: Fetches secret data for the app flow.
# Linked with: GeminiChatClient.__init__, OpenAIChatClient.__init__, VoiceRAGConfig.from_secrets, _email_credentials, _generate_ai_analysis, _generate_with_gemini, _get_float_env, _imap_credentials and more
def get_secret(name, default=None):
    value = os.environ.get(name)
    if value not in (None, ""):
        return value

    try:
        value = st.secrets.get(name)
    except Exception:
        value = None

    if value in (None, ""):
        value = _local_secrets().get(name, default)

    if value in (None, ""):
        return default
    return value
