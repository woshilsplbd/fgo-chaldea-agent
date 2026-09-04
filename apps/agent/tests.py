import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.test import Client, TestCase
from django.urls import reverse

from . import services


class AgentChatPageTests(TestCase):
    def test_agent_page_renders_without_backend_request(self):
        response = self.client.get(reverse("agent:chat"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agent/chat.html")
        self.assertContains(response, 'id="agent-chat"')
        self.assertContains(response, "迦勒底智能终端")
        self.assertContains(response, "Chaldea Agent")
        self.assertContains(response, 'action="/api/agent/chat/"')
        self.assertContains(response, 'id="agent-input"')
        self.assertContains(response, 'id="agent-send"')
        self.assertNotContains(response, 'id="agent-input" disabled')
        self.assertNotContains(response, 'id="agent-send" disabled')
        self.assertNotContains(response, "dify")
        self.assertNotContains(response, "openai")

    def test_agent_navigation_points_to_agent_page(self):
        response = self.client.get(reverse("agent:chat"))

        self.assertContains(response, 'id="agent"')
        self.assertContains(response, 'href="/agent/"')


class AgentChatApiTests(TestCase):
    api_url = reverse("agent_api:chat")

    def post_json(self, payload, **extra):
        return self.client.post(
            self.api_url,
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )

    @patch("apps.agent.views.services.chat")
    def test_valid_message_returns_normalized_success_envelope(self, chat):
        chat.return_value = {
            "answer": "A mocked answer",
            "conversation_id": "conversation-2",
            "message_id": "message-9",
        }

        response = self.post_json(
            {"message": "  hello FGO  ", "conversation_id": "conversation-1"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "answer": "A mocked answer",
                "conversation_id": "conversation-2",
                "message_id": "message-9",
            },
        )
        chat.assert_called_once_with("hello FGO", conversation_id="conversation-1")

    def test_missing_message_returns_invalid_request(self):
        response = self.post_json({})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    def test_empty_message_returns_invalid_request(self):
        response = self.post_json({"message": " \n\t"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    def test_non_string_message_returns_invalid_request(self):
        response = self.post_json({"message": 123})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    def test_malformed_json_returns_invalid_request(self):
        response = self.client.post(
            self.api_url,
            data="{broken",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    def test_non_json_content_type_returns_invalid_request(self):
        response = self.client.post(
            self.api_url,
            data="message=hello",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    def test_over_limit_message_returns_invalid_request(self):
        response = self.post_json({"message": "x" * 2001})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    def test_non_string_conversation_id_returns_invalid_request(self):
        response = self.post_json({"message": "hello", "conversation_id": 5})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    def test_default_service_returns_not_configured(self):
        response = self.post_json({"message": "hello"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "ok": False,
                "code": "agent_not_configured",
                "message": "Agent service is not configured.",
            },
        )

    @patch("apps.agent.views.services.chat")
    def test_service_failure_does_not_leak_exception_details(self, chat):
        chat.side_effect = RuntimeError("private provider details")

        response = self.post_json({"message": "hello"})
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "agent_service_error")
        self.assertNotIn("private provider details", body)
        self.assertNotIn("RuntimeError", body)
        self.assertNotIn("Traceback", body)

    def test_get_is_rejected_with_controlled_json_error(self):
        response = self.client.get(self.api_url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["code"], "method_not_allowed")

    def test_csrf_protection_remains_enabled(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            self.api_url,
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)


class DifyServiceTests(TestCase):
    base_url = "https://dify.example/v1/"
    api_key = "test-dify-key"

    def mock_response(self, payload=None, json_error=None):
        response = patch("apps.agent.services.requests.post").start()
        self.addCleanup(patch.stopall)
        response.return_value.raise_for_status.return_value = None
        if json_error:
            response.return_value.json.side_effect = json_error
        else:
            response.return_value.json.return_value = payload
        return response

    @override_settings(DIFY_API_KEY="", DIFY_API_BASE_URL=base_url)
    def test_missing_api_key_raises_not_configured(self):
        with self.assertRaises(services.AgentNotConfiguredError):
            services.chat("hello")

    @override_settings(DIFY_API_KEY=api_key, DIFY_API_BASE_URL="")
    def test_missing_base_url_raises_not_configured(self):
        with self.assertRaises(services.AgentNotConfiguredError):
            services.chat("hello")

    @override_settings(
        DIFY_API_KEY=api_key,
        DIFY_API_BASE_URL=base_url,
        DIFY_TIMEOUT_SECONDS=12.5,
    )
    def test_first_turn_builds_blocking_dify_request(self):
        post = self.mock_response(
            {"answer": "answer", "conversation_id": "conv", "message_id": "msg"}
        )

        result = services.chat("hello")

        self.assertEqual(result["answer"], "answer")
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://dify.example/v1/chat-messages")
        self.assertEqual(
            kwargs["headers"],
            {
                "Authorization": "Bearer test-dify-key",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(
            kwargs["json"],
            {
                "inputs": {},
                "query": "hello",
                "response_mode": "blocking",
                "user": "chaldea-agent-dev",
            },
        )
        self.assertNotIn("test-dify-key", json.dumps(kwargs["json"]))
        self.assertEqual(kwargs["timeout"], 12.5)

    @override_settings(DIFY_API_KEY=api_key, DIFY_API_BASE_URL=base_url)
    def test_continuation_forwards_conversation_id(self):
        post = self.mock_response({"answer": "next"})

        result = services.chat("follow up", conversation_id="conversation-1")

        self.assertEqual(result, {
            "answer": "next",
            "conversation_id": None,
            "message_id": None,
        })
        self.assertEqual(post.call_args.kwargs["json"]["conversation_id"], "conversation-1")

    @override_settings(DIFY_API_KEY=api_key, DIFY_API_BASE_URL=base_url)
    def test_timeout_raises_controlled_service_error(self):
        post = self.mock_response()
        post.side_effect = requests.Timeout("private timeout")

        with self.assertRaises(services.AgentServiceError):
            services.chat("hello")

    @override_settings(DIFY_API_KEY=api_key, DIFY_API_BASE_URL=base_url)
    def test_connection_failure_raises_controlled_service_error(self):
        post = self.mock_response()
        post.side_effect = requests.ConnectionError("private connection")

        with self.assertRaises(services.AgentServiceError):
            services.chat("hello")

    @override_settings(DIFY_API_KEY=api_key, DIFY_API_BASE_URL=base_url)
    def test_non_2xx_raises_controlled_service_error(self):
        post = self.mock_response()
        post.return_value.raise_for_status.side_effect = requests.HTTPError("private body")

        with self.assertRaises(services.AgentServiceError):
            services.chat("hello")

    @override_settings(DIFY_API_KEY=api_key, DIFY_API_BASE_URL=base_url)
    def test_malformed_json_raises_controlled_service_error(self):
        self.mock_response(json_error=ValueError("private body"))

        with self.assertRaises(services.AgentServiceError):
            services.chat("hello")

    @override_settings(DIFY_API_KEY=api_key, DIFY_API_BASE_URL=base_url)
    def test_invalid_success_payload_raises_controlled_service_error(self):
        self.mock_response({"answer": {"unexpected": True}})

        with self.assertRaises(services.AgentServiceError):
            services.chat("hello")

    @override_settings(DIFY_API_KEY=api_key, DIFY_API_BASE_URL=base_url)
    @patch("apps.agent.services.requests.post")
    def test_public_api_hides_upstream_body(self, post):
        post.return_value.raise_for_status.side_effect = requests.HTTPError(
            "raw provider secret body"
        )

        response = self.client.post(
            reverse("agent_api:chat"),
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        body = response.content.decode("utf-8")
        self.assertEqual(response.json()["code"], "agent_service_error")
        self.assertNotIn("raw provider secret body", body)
        self.assertNotIn("test-dify-key", body)


class AgentEvaluationCommandTests(TestCase):
    def write_cases(self, directory, cases=None):
        cases = cases or [
            {
                "id": "case-1",
                "category": "knowledge_hit",
                "question": "first",
                "source": "source-1",
                "expected_facts": ["fact-1"],
                "forbidden_claims": [],
            },
            {
                "id": "case-2",
                "category": "knowledge_hit",
                "question": "second",
                "source": "source-2",
                "expected_facts": ["fact-2"],
                "forbidden_claims": ["claim-2"],
            },
            {
                "id": "group-a-1",
                "category": "follow_up",
                "conversation_group": "group-a",
                "turn": 1,
                "question": "group first",
                "source": "source-a",
                "expected_facts": [],
                "forbidden_claims": [],
            },
            {
                "id": "group-a-2",
                "category": "follow_up",
                "conversation_group": "group-a",
                "turn": 2,
                "question": "group second",
                "source": "source-a",
                "expected_facts": [],
                "forbidden_claims": [],
            },
            {
                "id": "group-b-1",
                "category": "follow_up",
                "conversation_group": "group-b",
                "turn": 1,
                "question": "other group",
                "source": "source-b",
                "expected_facts": [],
                "forbidden_claims": [],
            },
        ]
        path = Path(directory) / "cases.json"
        path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
        return path

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.services.chat")
    def test_runner_writes_metadata_and_isolates_conversations(self, chat):
        calls = []

        def provider(message, conversation_id=None):
            calls.append((message, conversation_id))
            return {
                "answer": "answer for " + message,
                "conversation_id": "conv-a" if message == "group first" else None,
                "message_id": "message-1",
            }

        chat.side_effect = provider
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory)
            output = Path(directory) / "results.json"
            call_command("evaluate_agent", cases=str(cases), output=str(output))
            output_text = output.read_text(encoding="utf-8")
            payload = json.loads(output_text)

        self.assertEqual([item[1] for item in calls], [None, None, None, "conv-a", None])
        self.assertFalse(payload["retrieval_used"])
        self.assertEqual(payload["results"][1]["expected_facts"], ["fact-2"])
        self.assertEqual(payload["results"][1]["source"], "source-2")
        self.assertEqual(payload["results"][0]["status"], "success")
        self.assertIn("elapsed_seconds", payload["results"][0])
        self.assertNotIn("dummy", output_text)

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.services.chat")
    def test_curated_scope_metadata_survives_output(self, chat):
        chat.return_value = {
            "answer": "safe",
            "conversation_id": None,
            "message_id": None,
        }
        curated_case = {
            "id": "curated-case",
            "category": "knowledge_hit",
            "authority_scope": "CURRENT_OFFICIAL",
            "question": "current question",
            "source": "gameplay_basics.md — 游戏基础",
            "expected_facts": ["fact"],
            "forbidden_claims": [],
            "expected_scope_behavior": "Answer within current official scope.",
        }
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory, cases=[curated_case])
            output = Path(directory) / "results.json"
            call_command("evaluate_agent", cases=str(cases), output=str(output))
            result = json.loads(output.read_text(encoding="utf-8"))["results"][0]

        self.assertEqual(result["authority_scope"], "CURRENT_OFFICIAL")
        self.assertEqual(
            result["expected_scope_behavior"], "Answer within current official scope."
        )

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    def test_invalid_authority_scope_fails_clearly(self):
        with TemporaryDirectory() as directory:
            cases = self.write_cases(
                directory,
                cases=[
                    {
                        "id": "invalid-scope",
                        "category": "knowledge_hit",
                        "authority_scope": "NOT_ALLOWED",
                        "question": "question",
                        "source": "source",
                        "expected_facts": [],
                        "forbidden_claims": [],
                    }
                ],
            )
            output = Path(directory) / "results.json"

            with self.assertRaisesRegex(CommandError, "authority_scope"):
                call_command("evaluate_agent", cases=str(cases), output=str(output))

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.services.chat")
    def test_provider_failure_is_recorded_without_exception_details(self, chat):
        chat.side_effect = [
            services.AgentServiceError("private upstream body"),
            {"answer": "safe", "conversation_id": None, "message_id": None},
        ]
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory, cases=[
                {
                    "id": "failure",
                    "category": "knowledge_hit",
                    "question": "first",
                    "source": "source",
                    "expected_facts": [],
                    "forbidden_claims": [],
                },
                {
                    "id": "success",
                    "category": "knowledge_hit",
                    "question": "second",
                    "source": "source",
                    "expected_facts": [],
                    "forbidden_claims": [],
                },
            ])
            output = Path(directory) / "results.json"
            call_command("evaluate_agent", cases=str(cases), output=str(output))
            text = output.read_text(encoding="utf-8")
            payload = json.loads(text)

        self.assertEqual(payload["results"][0]["status"], "error")
        self.assertEqual(payload["results"][0]["error"]["code"], "agent_service_error")
        self.assertNotIn("private upstream body", text)
        self.assertEqual(payload["results"][1]["status"], "success")

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    def test_malformed_cases_json_fails_clearly(self):
        with TemporaryDirectory() as directory:
            cases = Path(directory) / "cases.json"
            cases.write_text("{broken", encoding="utf-8")
            output = Path(directory) / "results.json"

            with self.assertRaisesRegex(CommandError, "invalid cases JSON"):
                call_command("evaluate_agent", cases=str(cases), output=str(output))

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    def test_invalid_case_schema_fails_clearly(self):
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory, cases=[{"id": "incomplete"}])
            output = Path(directory) / "results.json"

            with self.assertRaisesRegex(CommandError, "missing fields"):
                call_command("evaluate_agent", cases=str(cases), output=str(output))

    @override_settings(DIFY_API_BASE_URL="", DIFY_API_KEY="")
    @patch("apps.agent.management.commands.evaluate_agent.services.chat")
    def test_missing_configuration_fails_before_evaluation(self, chat):
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory)
            output = Path(directory) / "results.json"

            with self.assertRaisesRegex(CommandError, "DIFY_API_BASE_URL"):
                call_command("evaluate_agent", cases=str(cases), output=str(output))

        chat.assert_not_called()

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.services.chat")
    def test_existing_output_requires_explicit_overwrite(self, chat):
        chat.return_value = {"answer": "safe", "conversation_id": None, "message_id": None}
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory)
            output = Path(directory) / "results.json"
            call_command("evaluate_agent", cases=str(cases), output=str(output))

            with self.assertRaisesRegex(CommandError, "output already exists"):
                call_command("evaluate_agent", cases=str(cases), output=str(output))
            call_command(
                "evaluate_agent",
                cases=str(cases),
                output=str(output),
                overwrite=True,
            )
