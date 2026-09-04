import requests
from django.conf import settings


class AgentNotConfiguredError(Exception):
    """Raised when no runtime Agent provider has been configured."""


class AgentServiceError(Exception):
    """Raised for controlled failures from a configured Agent provider."""


def chat(message, conversation_id=None):
    """Send one blocking chat turn through the configured Dify provider."""
    base_url = (getattr(settings, "DIFY_API_BASE_URL", "") or "").strip().rstrip("/")
    api_key = (getattr(settings, "DIFY_API_KEY", "") or "").strip()
    if not base_url or not api_key:
        raise AgentNotConfiguredError

    payload = {
        "inputs": {},
        "query": message,
        "response_mode": "blocking",
        "user": "chaldea-agent-dev",
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
        response.raise_for_status()
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

    conversation_id = data.get("conversation_id")
    message_id = data.get("message_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise AgentServiceError("Dify returned an invalid conversation ID")
    if message_id is not None and not isinstance(message_id, str):
        raise AgentServiceError("Dify returned an invalid message ID")

    return {
        "answer": data["answer"],
        "conversation_id": conversation_id,
        "message_id": message_id,
    }
