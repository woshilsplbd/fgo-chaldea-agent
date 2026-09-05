import json
import re
import time
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.agent import services


SUPPORTED_CATEGORIES = {
    "knowledge_hit",
    "retrieval_discrimination",
    "knowledge_miss",
    "follow_up",
    "out_of_scope_structured_fact",
}
SUPPORTED_AUTHORITY_SCOPES = {
    "CURRENT_OFFICIAL",
    "ARCHIVE_HISTORICAL",
    "ARCHIVE_EDITORIAL",
    "STRUCTURED_TOOL_BOUNDARY",
}
SUPPORTED_ROUTINGS = {"servant_tool", "rag", "both"}
DIFY_USER = "chaldea-agent-dev"
TRACE_LIMIT = 20
REQUIRED_CASE_FIELDS = {
    "id",
    "category",
    "question",
    "source",
    "expected_facts",
    "forbidden_claims",
}


def load_cases(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise CommandError("cases file must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"invalid cases JSON: {exc.msg}") from exc

    if not isinstance(payload, list):
        raise CommandError("cases file must contain a top-level JSON list")

    seen_ids = set()
    cases = []
    for index, case in enumerate(payload, start=1):
        if not isinstance(case, dict):
            raise CommandError(f"case {index} must be a JSON object")

        missing = REQUIRED_CASE_FIELDS.difference(case)
        if missing:
            names = ", ".join(sorted(missing))
            raise CommandError(f"case {index} missing fields: {names}")

        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id.strip():
            raise CommandError(f"case {index} id must be a non-empty string")
        if case_id in seen_ids:
            raise CommandError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)

        category = case["category"]
        if category not in SUPPORTED_CATEGORIES:
            raise CommandError(
                f"case {case_id} has unsupported category: {category}"
            )
        if not isinstance(case["question"], str) or not case["question"].strip():
            raise CommandError(f"case {case_id} question must be a non-empty string")
        if not isinstance(case["source"], str):
            raise CommandError(f"case {case_id} source must be a string")
        for field in ("expected_facts", "forbidden_claims"):
            values = case[field]
            if not isinstance(values, list) or not all(
                isinstance(value, str) for value in values
            ):
                raise CommandError(
                    f"case {case_id} {field} must be a JSON list of strings"
                )

        authority_scope = case.get("authority_scope")
        if authority_scope is not None and (
            not isinstance(authority_scope, str)
            or authority_scope not in SUPPORTED_AUTHORITY_SCOPES
        ):
            raise CommandError(
                f"case {case_id} has unsupported authority_scope: {authority_scope}"
            )
        expected_scope_behavior = case.get("expected_scope_behavior")
        if expected_scope_behavior is not None and (
            not isinstance(expected_scope_behavior, str)
            or not expected_scope_behavior.strip()
        ):
            raise CommandError(
                f"case {case_id} expected_scope_behavior must be a non-empty string"
            )
        expected_routing = case.get("expected_routing")
        if expected_routing is not None and expected_routing not in SUPPORTED_ROUTINGS:
            raise CommandError(
                f"case {case_id} has unsupported expected_routing: {expected_routing}"
            )

        group = case.get("conversation_group")
        turn = case.get("turn")
        if group is not None and (
            not isinstance(group, str) or not group.strip()
        ):
            raise CommandError(
                f"case {case_id} conversation_group must be a non-empty string"
            )
        if turn is not None and (
            isinstance(turn, bool) or not isinstance(turn, int) or turn < 1
        ):
            raise CommandError(f"case {case_id} turn must be a positive integer")
        if (group is None) != (turn is None):
            raise CommandError(
                f"case {case_id} conversation_group and turn must be provided together"
            )
        if category == "follow_up" and group is None:
            raise CommandError(
                f"case {case_id} follow_up cases require conversation_group and turn"
            )

        cases.append(case)

    return cases


def safe_result(result):
    if not isinstance(result, dict):
        raise services.AgentServiceError("provider result was not an object")
    answer = result.get("answer")
    conversation_id = result.get("conversation_id")
    message_id = result.get("message_id")
    if not isinstance(answer, str):
        raise services.AgentServiceError("provider result had no text answer")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise services.AgentServiceError("provider result had an invalid conversation ID")
    if message_id is not None and not isinstance(message_id, str):
        raise services.AgentServiceError("provider result had an invalid message ID")
    return answer, conversation_id, message_id


def _first_value(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _redact_sensitive(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in ("key", "token", "secret", "authorization")):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def routing_metadata(result):
    routing = result.get("routing") if isinstance(result.get("routing"), dict) else {}
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    tool_calls = _first_value(
        routing.get("tool_calls"),
        result.get("tool_calls"),
        metadata.get("tool_calls"),
    )
    first_tool_call = tool_calls[0] if isinstance(tool_calls, list) and tool_calls else {}
    if not isinstance(first_tool_call, dict):
        first_tool_call = {}

    tool_invoked = _first_value(
        routing.get("tool_invoked"),
        result.get("tool_invoked"),
        metadata.get("tool_invoked"),
    )
    if not isinstance(tool_invoked, bool):
        tool_invoked = bool(tool_calls) if isinstance(tool_calls, list) else None

    tool_name = _first_value(
        routing.get("tool_name"),
        result.get("tool_name"),
        metadata.get("tool_name"),
        first_tool_call.get("tool_name"),
        first_tool_call.get("name"),
    )
    tool_input = _first_value(
        routing.get("tool_input"),
        result.get("tool_input"),
        metadata.get("tool_input"),
        first_tool_call.get("tool_input"),
        first_tool_call.get("input"),
        first_tool_call.get("arguments"),
    )
    tool_response_metadata = _first_value(
        routing.get("tool_response_metadata"),
        result.get("tool_response_metadata"),
        metadata.get("tool_response_metadata"),
        first_tool_call.get("tool_response_metadata"),
        first_tool_call.get("response_metadata"),
    )
    retrieval_used = _first_value(
        routing.get("retrieval_used"),
        result.get("retrieval_used"),
        metadata.get("retrieval_used"),
    )
    if not isinstance(retrieval_used, bool):
        retriever_resources = metadata.get("retriever_resources")
        if isinstance(retriever_resources, list):
            retrieval_used = bool(retriever_resources)
        else:
            retrieval_used = None

    actual_routing = _first_value(
        routing.get("actual_routing"),
        result.get("actual_routing"),
        metadata.get("actual_routing"),
    )
    if actual_routing not in SUPPORTED_ROUTINGS:
        if tool_invoked is True and retrieval_used is True:
            actual_routing = "both"
        elif tool_invoked is True:
            actual_routing = "servant_tool"
        elif retrieval_used is True:
            actual_routing = "rag"
        else:
            actual_routing = "unknown"

    return {
        "tool_invoked": tool_invoked,
        "tool_name": tool_name,
        "tool_input": _redact_sensitive(tool_input),
        "tool_response_metadata": _redact_sensitive(tool_response_metadata),
        "retrieval_used": retrieval_used,
        "actual_routing": actual_routing,
    }


def _sanitize_trace_text(value, limit=2000):
    text = str(value)
    text = re.sub(
        r"(?i)(authorization|api[_-]?key|token|secret)\s*[:=]\s*[^,\s]+",
        r"\1=[redacted]",
        text,
    )
    return text[:limit]


def _compact_trace_value(value):
    if isinstance(value, dict):
        return _redact_sensitive(value)
    if isinstance(value, list):
        return [_compact_trace_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_trace_text(value)
    return value


def _parse_trace_message(message):
    if not isinstance(message, dict):
        return None

    thoughts = message.get("agent_thoughts")
    resources_present = "retriever_resources" in message
    resources = message.get("retriever_resources")
    if not isinstance(thoughts, list) or (
        not resources_present and "agent_thoughts" not in message
    ):
        return None

    tool_names = []
    tool_inputs = []
    observations = []
    for thought in thoughts:
        if not isinstance(thought, dict):
            continue
        tool = thought.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            continue
        tool_names.append(tool.strip())
        raw_input = thought.get("tool_input")
        if isinstance(raw_input, str):
            try:
                raw_input = json.loads(raw_input)
            except (TypeError, ValueError):
                raw_input = _sanitize_trace_text(raw_input)
        tool_inputs.append(_compact_trace_value(raw_input))
        if "observation" in thought:
            observations.append(_compact_trace_value(thought["observation"]))

    if isinstance(resources, list):
        retrieval_used = bool(resources)
    else:
        retrieval_used = None

    tool_invoked = bool(tool_names)
    if tool_invoked and retrieval_used is True:
        actual_routing = "both"
    elif tool_invoked:
        actual_routing = "servant_tool"
    elif retrieval_used is True:
        actual_routing = "rag"
    else:
        actual_routing = "none" if retrieval_used is False else "unknown"

    return {
        "trace_status": "ok",
        "tool_invoked": tool_invoked,
        "tool_name": tool_names[0] if len(tool_names) == 1 else tool_names,
        "tool_input": tool_inputs[0] if len(tool_inputs) == 1 else tool_inputs,
        "tool_response_metadata": observations[0] if len(observations) == 1 else observations,
        "retrieval_used": retrieval_used,
        "actual_routing": actual_routing,
    }


def fetch_dify_message_trace(conversation_id, message_id):
    unavailable = {
        "trace_status": "unavailable",
        "tool_invoked": None,
        "tool_name": None,
        "tool_input": None,
        "tool_response_metadata": None,
        "retrieval_used": None,
        "actual_routing": "unknown",
    }
    if not conversation_id or not message_id:
        return unavailable

    base_url = (getattr(settings, "DIFY_API_BASE_URL", "") or "").strip().rstrip("/")
    api_key = (getattr(settings, "DIFY_API_KEY", "") or "").strip()
    if not base_url or not api_key:
        return unavailable

    try:
        response = requests.get(
            f"{base_url}/messages",
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "conversation_id": conversation_id,
                "user": DIFY_USER,
                "limit": TRACE_LIMIT,
            },
            timeout=getattr(settings, "DIFY_TIMEOUT_SECONDS", 30.0),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, TypeError, ValueError):
        return unavailable

    messages = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        return unavailable
    for message in messages:
        if isinstance(message, dict) and message.get("id") == message_id:
            return _parse_trace_message(message) or unavailable
    return unavailable


class Command(BaseCommand):
    help = "Record raw Agent answers for the version-controlled evaluation cases."

    def add_arguments(self, parser):
        parser.add_argument("--cases", required=True, help="Path to evaluation cases JSON")
        parser.add_argument("--output", required=True, help="Path for the baseline output JSON")
        parser.add_argument(
            "--retrieval-used",
            action="store_true",
            help="Record that Knowledge Retrieval was enabled for this run",
        )
        parser.add_argument(
            "--experiment-label",
            default=None,
            help="Optional operator-supplied label for this evaluation run",
        )
        parser.add_argument(
            "--delay-seconds",
            type=float,
            default=0.0,
            help="Seconds to wait between evaluation requests (default: 0)",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Allow replacing an existing output file",
        )

    def handle(self, *args, **options):
        delay_seconds = options["delay_seconds"]
        if delay_seconds < 0:
            raise CommandError("delay-seconds must be greater than or equal to 0")

        cases_path = Path(options["cases"])
        output_path = Path(options["output"])
        if not cases_path.is_file():
            raise CommandError(f"cases file does not exist: {cases_path}")
        if output_path.exists() and not options["overwrite"]:
            raise CommandError(
                f"output already exists: {output_path}; use --overwrite to replace it"
            )

        if not getattr(settings, "DIFY_API_BASE_URL", "") or not getattr(
            settings, "DIFY_API_KEY", ""
        ):
            raise CommandError(
                "Dify configuration is missing; set DIFY_API_BASE_URL and DIFY_API_KEY."
            )

        cases = load_cases(cases_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        group_conversations = {}
        results = []

        for index, case in enumerate(cases):
            if index and delay_seconds:
                time.sleep(delay_seconds)
            group = case.get("conversation_group")
            conversation_id = group_conversations.get(group) if group else None
            started = time.perf_counter()
            record = {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "source": case["source"],
                "expected_facts": case["expected_facts"],
                "forbidden_claims": case["forbidden_claims"],
                "conversation_id": None,
                "message_id": None,
                "elapsed_seconds": None,
                "latency_seconds": None,
                "success": False,
                "tool_invoked": None,
                "tool_name": None,
                "tool_input": None,
                "tool_response_metadata": None,
                "expected_routing": case.get("expected_routing"),
                "actual_routing": "unknown",
                "routing_match": False,
                "retrieval_used": None,
                "trace_status": "unavailable",
            }
            if "authority_scope" in case:
                record["authority_scope"] = case["authority_scope"]
            if "expected_scope_behavior" in case:
                record["expected_scope_behavior"] = case[
                    "expected_scope_behavior"
                ]
            try:
                provider_result = services.chat(
                    case["question"], conversation_id=conversation_id
                )
                answer, returned_conversation_id, message_id = safe_result(
                    provider_result
                )
                record.update(
                    {
                        "status": "success",
                        "success": True,
                        "answer": answer,
                        "conversation_id": returned_conversation_id,
                        "message_id": message_id,
                    }
                )
                trace = fetch_dify_message_trace(
                    returned_conversation_id,
                    message_id,
                )
                record.update(trace)
                expected_routing = record["expected_routing"]
                record["routing_match"] = (
                    expected_routing is not None
                    and trace["actual_routing"] == expected_routing
                )
                if group and returned_conversation_id:
                    group_conversations[group] = returned_conversation_id
            except services.AgentNotConfiguredError as exc:
                raise CommandError(
                    "Agent provider became unconfigured during evaluation."
                ) from exc
            except Exception:
                record.update(
                    {
                        "status": "error",
                        "success": False,
                        "error": {
                            "code": "agent_service_error",
                            "message": "Agent service failed for this case.",
                        },
                    }
                )
            finally:
                record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
                record["latency_seconds"] = record["elapsed_seconds"]
            results.append(record)

        output = {
            "version": 1,
            "retrieval_used": bool(options["retrieval_used"]),
            "experiment_label": options.get("experiment_label"),
            "cases_path": str(cases_path),
            "results": results,
        }
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Recorded {len(results)} evaluation results to {output_path}"
            )
        )
