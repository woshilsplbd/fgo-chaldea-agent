import json
import time
from pathlib import Path

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
                        "answer": answer,
                        "conversation_id": returned_conversation_id,
                        "message_id": message_id,
                    }
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
                        "error": {
                            "code": "agent_service_error",
                            "message": "Agent service failed for this case.",
                        },
                    }
                )
            finally:
                record["elapsed_seconds"] = round(
                    time.perf_counter() - started, 6
                )
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
