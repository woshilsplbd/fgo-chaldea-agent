"""Production-only Dify streaming helpers.

The evaluator has its own streaming adapter because it records execution
metadata.  This module intentionally exposes only user-visible answer text
and stable completion identifiers for the public Agent path.
"""

import json
import re

import requests
from django.conf import settings

from .services import (
    AgentNotConfiguredError,
    AgentServiceError,
    ConversationUnavailableError,
    _is_conversation_unavailable_payload,
    _raise_for_status,
)


_OPEN_THINK_RE = re.compile(r"<think\b[^>]*>", re.IGNORECASE)
_CLOSE_THINK_RE = re.compile(r"</think\s*>", re.IGNORECASE)
_REASONING_MARKER_RE = re.compile(
    r"<!--\s*dify-deepseek-reasoning\s*-->",
    re.IGNORECASE,
)
_PARTIAL_OPEN = "<think"
_PARTIAL_CLOSE = "</think"
_MAX_STREAM_ID_LENGTH = 256
_ID_EVENT_NAMES = frozenset(
    ("message", "message_end", "agent_thought", "message_file", "message_replace")
)


def _valid_stream_id(value):
    """Return a bounded, non-empty stream identifier or ``None``."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > _MAX_STREAM_ID_LENGTH:
        return None
    return value


def _remember_stream_ids(
    event_name, event, data, conversation_id, message_id
):
    """Capture IDs from known Dify metadata fields, never arbitrary outputs."""
    if event_name not in _ID_EVENT_NAMES:
        return conversation_id, message_id

    metadata = (event, data)
    event_conversation_id = None
    event_message_id = None
    for source in metadata:
        if not isinstance(source, dict):
            continue
        if event_conversation_id is None:
            event_conversation_id = _valid_stream_id(source.get("conversation_id"))
        if event_message_id is None:
            event_message_id = _valid_stream_id(source.get("message_id"))
        if event_message_id is None:
            event_message_id = _valid_stream_id(source.get("id"))

    # Earlier message/agent metadata establishes a fallback.  message_end is
    # allowed to confirm or update it when the upstream completion arrives.
    if event_name == "message_end":
        conversation_id = event_conversation_id or conversation_id
        message_id = event_message_id or message_id
    else:
        conversation_id = conversation_id or event_conversation_id
        message_id = message_id or event_message_id
    return conversation_id, message_id


def _partial_suffix(value):
    """Return a possible incomplete control token at the end of *value*."""
    lowered = value.lower()
    candidates = []

    for prefix in (_PARTIAL_OPEN, _PARTIAL_CLOSE):
        for index in range(len(lowered)):
            suffix = lowered[index:]
            if suffix and len(suffix) < len(prefix) and prefix.startswith(suffix):
                candidates.append(value[index:])
            if suffix.startswith(prefix) and ">" not in suffix:
                candidates.append(value[index:])

    for index in range(len(lowered)):
        suffix = lowered[index:]
        if suffix.startswith("<!--") and "-->" not in suffix:
            candidates.append(value[index:])

    return max(candidates, key=len, default="")


class ReasoningSanitizer:
    """Incrementally suppress Dify/DeepSeek reasoning markup."""

    def __init__(self):
        self._buffer = ""
        self._in_reasoning = False

    def feed(self, text):
        if not isinstance(text, str) or not text:
            return ""

        self._buffer += text
        visible = []
        while self._buffer:
            if self._in_reasoning:
                closing = _CLOSE_THINK_RE.search(self._buffer)
                if closing:
                    self._buffer = self._buffer[closing.end():]
                    self._in_reasoning = False
                    continue
                self._buffer = _partial_suffix(self._buffer)
                break

            opening = _OPEN_THINK_RE.search(self._buffer)
            marker = _REASONING_MARKER_RE.search(self._buffer)
            matches = [match for match in (opening, marker) if match]
            if matches:
                control = min(matches, key=lambda match: match.start())
                visible.append(self._buffer[:control.start()])
                self._buffer = self._buffer[control.end():]
                self._in_reasoning = control is opening
                continue

            partial = _partial_suffix(self._buffer)
            if partial:
                emit_length = len(self._buffer) - len(partial)
                visible.append(self._buffer[:emit_length])
                self._buffer = partial
                if emit_length == 0:
                    break
            else:
                visible.append(self._buffer)
                self._buffer = ""

        return "".join(visible)

    def finish(self):
        """Flush safe text and discard incomplete/private reasoning tokens."""
        if self._in_reasoning:
            self._buffer = ""
            return ""

        pending = self._buffer
        self._buffer = ""
        if not pending:
            return ""

        opening = _OPEN_THINK_RE.search(pending)
        marker = _REASONING_MARKER_RE.search(pending)
        matches = [match for match in (opening, marker) if match]
        if matches:
            control = min(matches, key=lambda match: match.start())
            return pending[:control.start()]

        # A partial opening token at EOF is treated defensively as private
        # reasoning rather than being emitted to the browser.
        partial = _partial_suffix(pending)
        if partial and len(partial) > 1 and pending.endswith(partial):
            return pending[:-len(partial)]
        return pending


def _answer_node_text(data):
    """Return an allowlisted Answer-node output, if one is present."""
    if not isinstance(data, dict):
        return None

    node_type = str(data.get("node_type") or "").lower()
    title = str(data.get("title") or "").lower()
    if "answer" not in node_type and "answer" not in title:
        return None

    outputs = data.get("outputs")
    if not isinstance(outputs, dict):
        return None
    for key in ("answer", "text", "content"):
        value = outputs.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _sanitize_answer_node_text(value):
    """Sanitize a complete Answer-node value using the production sanitizer."""
    sanitizer = ReasoningSanitizer()
    visible = sanitizer.feed(value) + sanitizer.finish()
    visible = visible.strip()
    return visible or None


def _configured_provider():
    base_url = (getattr(settings, "DIFY_API_BASE_URL", "") or "").strip().rstrip("/")
    api_key = (getattr(settings, "DIFY_API_KEY", "") or "").strip()
    if not base_url or not api_key:
        raise AgentNotConfiguredError
    return base_url, api_key


def stream_chat(message, conversation_id=None, *, user_id):
    """Return an iterator of safe answer deltas and a final completion event."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise AgentServiceError("Agent user identity is unavailable")
    base_url, api_key = _configured_provider()
    payload = {
        "inputs": {},
        "query": message,
        "response_mode": "streaming",
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
            stream=True,
        )
        _raise_for_status(response)
    except ConversationUnavailableError:
        close = getattr(locals().get("response"), "close", None)
        if callable(close):
            close()
        raise
    except requests.Timeout as exc:
        close = getattr(locals().get("response"), "close", None)
        if callable(close):
            close()
        raise AgentServiceError("Dify streaming request timed out") from exc
    except requests.RequestException as exc:
        close = getattr(locals().get("response"), "close", None)
        if callable(close):
            close()
        raise AgentServiceError("Dify streaming request failed") from exc

    def events():
        sanitizer = ReasoningSanitizer()
        message_end = None
        retained_conversation_id = None
        retained_message_id = None
        visible_answer = False
        answer_node_candidates = []
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8", errors="replace")
                if not raw_line.startswith("data:"):
                    continue

                raw_data = raw_line[5:].strip()
                if not raw_data or raw_data == "[DONE]":
                    continue
                try:
                    event = json.loads(raw_data)
                except (TypeError, ValueError):
                    continue
                if not isinstance(event, dict):
                    continue

                event_name = event.get("event")
                data = event.get("data")
                if not isinstance(data, dict):
                    data = {}
                retained_conversation_id, retained_message_id = _remember_stream_ids(
                    event_name,
                    event,
                    data,
                    retained_conversation_id,
                    retained_message_id,
                )
                if event_name == "message":
                    chunk = data.get("answer")
                    safe_chunk = sanitizer.feed(chunk)
                    if safe_chunk:
                        visible_answer = True
                        yield {"type": "delta", "text": safe_chunk}
                elif event_name == "message_end":
                    message_end = data
                    # A valid Chatflow may emit its Answer node after
                    # message_end.  Keep reading until EOF when no visible
                    # message text has arrived so that fallback can run.
                    if visible_answer:
                        break
                elif event_name == "node_finished":
                    answer = _answer_node_text(data)
                    if answer is not None:
                        answer_node_candidates.append(answer)
                elif event_name == "error":
                    error_payloads = (data, event) if data else (event,)
                    if any(
                        _is_conversation_unavailable_payload(
                            error_payload,
                            status_code=(
                                error_payload.get("status")
                                if isinstance(error_payload, dict)
                                else None
                            ),
                        )
                        for error_payload in error_payloads
                    ):
                        raise ConversationUnavailableError
                    raise AgentServiceError("Dify streaming response reported an error")
                # workflow/node/tool events are intentionally ignored.

            if not isinstance(message_end, dict):
                raise AgentServiceError(
                    "Dify streaming response ended before message_end"
                )

            trailing = sanitizer.finish()
            if trailing:
                visible_answer = True
                yield {"type": "delta", "text": trailing}
            if not visible_answer:
                for candidate in reversed(answer_node_candidates):
                    fallback = _sanitize_answer_node_text(candidate)
                    if fallback:
                        visible_answer = True
                        yield {"type": "delta", "text": fallback}
                        break
            if not visible_answer:
                raise AgentServiceError("Dify returned an empty chat response")

            completion_conversation_id = retained_conversation_id
            completion_message_id = retained_message_id
            if isinstance(message_end, dict):
                completion_conversation_id = _valid_stream_id(
                    message_end.get("conversation_id")
                ) or completion_conversation_id
                completion_message_id = _valid_stream_id(
                    message_end.get("message_id")
                ) or _valid_stream_id(message_end.get("id")) or completion_message_id

            yield {
                "type": "done",
                "conversation_id": completion_conversation_id,
                "message_id": completion_message_id,
            }
        except requests.Timeout as exc:
            raise AgentServiceError("Dify streaming request timed out") from exc
        except requests.RequestException as exc:
            raise AgentServiceError("Dify streaming request failed") from exc
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    return events()
