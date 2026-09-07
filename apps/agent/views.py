import json

from django.http import JsonResponse, StreamingHttpResponse
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


def _parse_chat_request(request):
    if request.method != "POST":
        return None, _error_response(
            "method_not_allowed",
            "Only POST requests are supported.",
            405,
        )

    if request.content_type != "application/json":
        return None, _error_response(
            "invalid_request",
            "Request content type must be application/json.",
            400,
        )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, _error_response(
            "invalid_request",
            "Request body must contain valid JSON.",
            400,
        )

    if not isinstance(payload, dict):
        return None, _error_response(
            "invalid_request",
            "Request body must be a JSON object.",
            400,
        )

    message = payload.get("message")
    if not isinstance(message, str):
        return None, _error_response(
            "invalid_request",
            "message must be a string.",
            400,
        )

    message = message.strip()
    if not message:
        return None, _error_response(
            "invalid_request",
            "message must not be empty.",
            400,
        )
    if len(message) > MAX_MESSAGE_LENGTH:
        return None, _error_response(
            "invalid_request",
            f"message must be {MAX_MESSAGE_LENGTH} characters or fewer.",
            400,
        )

    conversation_id = payload.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        return None, _error_response(
            "invalid_request",
            "conversation_id must be a string when provided.",
            400,
        )

    return (message, conversation_id), None


def chat_api(request):
    parsed, error = _parse_chat_request(request)
    if error:
        return error
    message, conversation_id = parsed

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


def _sse_event(event_type, payload):
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def _stream_chat_events(message, conversation_id):
    yield _sse_event("start", {"ok": True})
    upstream = None
    try:
        upstream = services.stream_chat(message, conversation_id=conversation_id)
        completed = False
        for event in upstream:
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            if event_type == "delta":
                text = event.get("text")
                if isinstance(text, str) and text:
                    yield _sse_event("delta", {"text": text})
            elif event_type == "done":
                completion_conversation_id = event.get("conversation_id")
                completion_message_id = event.get("message_id")
                if completion_conversation_id is not None and not isinstance(
                    completion_conversation_id, str
                ):
                    raise services.AgentServiceError(
                        "Dify returned an invalid conversation ID"
                    )
                if completion_message_id is not None and not isinstance(
                    completion_message_id, str
                ):
                    raise services.AgentServiceError("Dify returned an invalid message ID")
                yield _sse_event(
                    "done",
                    {
                        "conversation_id": completion_conversation_id,
                        "message_id": completion_message_id,
                    },
                )
                completed = True
                break

        if not completed:
            raise services.AgentServiceError(
                "Dify streaming response ended before completion"
            )
    except GeneratorExit:
        raise
    except services.AgentNotConfiguredError:
        yield _sse_event(
            "error",
            {
                "code": "agent_not_configured",
                "message": "Agent service is not configured.",
            },
        )
    except services.AgentServiceError:
        yield _sse_event(
            "error",
            {
                "code": "agent_stream_error",
                "message": "Agent service is temporarily unavailable.",
            },
        )
    except Exception:
        yield _sse_event(
            "error",
            {
                "code": "agent_stream_error",
                "message": "Agent service is temporarily unavailable.",
            },
        )
    finally:
        close = getattr(upstream, "close", None)
        if callable(close):
            close()


def chat_stream_api(request):
    parsed, error = _parse_chat_request(request)
    if error:
        return error
    message, conversation_id = parsed

    response = StreamingHttpResponse(
        _stream_chat_events(message, conversation_id),
        content_type="text/event-stream; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
