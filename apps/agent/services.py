import re

import requests
from django.conf import settings


class AgentNotConfiguredError(Exception):
    """Raised when no runtime Agent provider has been configured."""


class AgentServiceError(Exception):
    """Raised for controlled failures from a configured Agent provider."""


class ConversationUnavailableError(AgentServiceError):
    """Raised when a conversation cannot be continued by the current user."""


_STALE_CONVERSATION_CODES = frozenset(
    ("conversation_not_found", "conversation_not_exists", "conversation_not_exist")
)
_CONVERSATION_NOT_FOUND_RE = re.compile(
    r"\bconversation\s+(?:not\s+exists|does\s+not\s+exist|not\s+found)\b",
    re.IGNORECASE,
)


def _is_conversation_unavailable_payload(payload, status_code=None):
    """Match only Dify's structured missing/ownership conversation signal."""
    if not isinstance(payload, dict):
        return False
    if status_code is not None and status_code not in (400, 404):
        return False

    code = payload.get("code")
    code = code.strip().lower() if isinstance(code, str) else ""
    if code in _STALE_CONVERSATION_CODES:
        return True

    # Dify commonly returns HTTP 404 with the generic not_found code for this
    # endpoint, so require the structured conversation-specific message too.
    message = payload.get("message")
    return (
        status_code in (None, 404)
        and code == "not_found"
        and isinstance(message, str)
        and bool(_CONVERSATION_NOT_FOUND_RE.search(message))
    )


def _is_conversation_unavailable_response(response):
    """Safely inspect an HTTP error response without exposing its body."""
    status_code = getattr(response, "status_code", None)
    try:
        payload = response.json()
    except (AttributeError, TypeError, ValueError):
        return False
    return _is_conversation_unavailable_payload(payload, status_code=status_code)


def _raise_for_status(response):
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        if _is_conversation_unavailable_response(response):
            raise ConversationUnavailableError from exc
        raise


_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
_UNCLOSED_THINK_RE = re.compile(r"<think\b[^>]*>.*\Z", re.IGNORECASE | re.DOTALL)
_REASONING_MARKER_RE = re.compile(
    r"[ \t]*<!--\s*dify-deepseek-reasoning\s*-->[ \t]*",
    re.IGNORECASE,
)


def sanitize_answer(answer):
    """Remove provider reasoning markup from a user-visible answer."""
    sanitized = _THINK_BLOCK_RE.sub("", answer)
    sanitized = _UNCLOSED_THINK_RE.sub("", sanitized)
    sanitized = _REASONING_MARKER_RE.sub(" ", sanitized)
    sanitized = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", sanitized)
    return sanitized.strip()


def chat(message, conversation_id=None, *, user_id):
    """Send one blocking chat turn through the configured Dify provider."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise AgentServiceError("Agent user identity is unavailable")
    base_url = (getattr(settings, "DIFY_API_BASE_URL", "") or "").strip().rstrip("/")
    api_key = (getattr(settings, "DIFY_API_KEY", "") or "").strip()
    if not base_url or not api_key:
        raise AgentNotConfiguredError

    payload = {
        "inputs": {},
        "query": message,
        "response_mode": "blocking",
        "user": user_id,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    try:
        response = requests.post(
            f"{base_url}/chat-messages",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=getattr(settings, "DIFY_TIMEOUT_SECONDS", 30.0),
        )
        _raise_for_status(response)
    except requests.Timeout as exc:
        raise AgentServiceError("Dify request timed out") from exc
    except requests.RequestException as exc:
        raise AgentServiceError("Dify request failed") from exc

    try:
        data = response.json()
    except (TypeError, ValueError) as exc:
        raise AgentServiceError("Dify returned invalid JSON") from exc

    if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
        raise AgentServiceError("Dify returned an invalid chat response")

    answer = sanitize_answer(data["answer"])
    if not answer:
        raise AgentServiceError("Dify returned an empty chat response")

    conversation_id = data.get("conversation_id")
    message_id = data.get("message_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise AgentServiceError("Dify returned an invalid conversation ID")
    if message_id is not None and not isinstance(message_id, str):
        raise AgentServiceError("Dify returned an invalid message ID")

    return {
        "answer": answer,
        "conversation_id": conversation_id,
        "message_id": message_id,
    }


def stream_chat(message, conversation_id=None, *, user_id):
    """Return the production streaming service iterator."""
    from .streaming import stream_chat as _stream_chat

    return _stream_chat(message, conversation_id=conversation_id, user_id=user_id)
