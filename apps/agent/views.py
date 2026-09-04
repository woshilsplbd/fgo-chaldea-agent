import json

from django.http import JsonResponse
from django.shortcuts import render

from . import services


MAX_MESSAGE_LENGTH = 2000


def chat(request):
    return render(request, "agent/chat.html", {"active_menu": "agent"})


def _error_response(code, message, status):
    return JsonResponse(
        {"ok": False, "code": code, "message": message},
        status=status,
    )


def chat_api(request):
    if request.method != "POST":
        return _error_response(
            "method_not_allowed",
            "Only POST requests are supported.",
            405,
        )

    if request.content_type != "application/json":
        return _error_response(
            "invalid_request",
            "Request content type must be application/json.",
            400,
        )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error_response(
            "invalid_request",
            "Request body must contain valid JSON.",
            400,
        )

    if not isinstance(payload, dict):
        return _error_response(
            "invalid_request",
            "Request body must be a JSON object.",
            400,
        )

    message = payload.get("message")
    if not isinstance(message, str):
        return _error_response(
            "invalid_request",
            "message must be a string.",
            400,
        )

    message = message.strip()
    if not message:
        return _error_response(
            "invalid_request",
            "message must not be empty.",
            400,
        )
    if len(message) > MAX_MESSAGE_LENGTH:
        return _error_response(
            "invalid_request",
            f"message must be {MAX_MESSAGE_LENGTH} characters or fewer.",
            400,
        )

    conversation_id = payload.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        return _error_response(
            "invalid_request",
            "conversation_id must be a string when provided.",
            400,
        )

    try:
        result = services.chat(message, conversation_id=conversation_id)
    except services.AgentNotConfiguredError:
        return _error_response(
            "agent_not_configured",
            "Agent service is not configured.",
            503,
        )
    except Exception:
        return _error_response(
            "agent_service_error",
            "Agent service is temporarily unavailable.",
            502,
        )

    return JsonResponse(
        {
            "ok": True,
            "answer": result.get("answer"),
            "conversation_id": result.get("conversation_id"),
            "message_id": result.get("message_id"),
        }
    )
