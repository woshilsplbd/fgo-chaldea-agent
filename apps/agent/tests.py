import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call, patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.test import Client, TestCase
from django.urls import reverse

from . import services
from .management.commands import evaluate_agent


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
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
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
        self.assertIsNone(payload["experiment_label"])
        self.assertEqual(payload["results"][1]["expected_facts"], ["fact-2"])
        self.assertEqual(payload["results"][1]["source"], "source-2")
        self.assertEqual(payload["results"][0]["status"], "success")
        self.assertIn("elapsed_seconds", payload["results"][0])
        self.assertTrue(payload["results"][0]["success"])
        self.assertIsNone(payload["results"][0]["tool_invoked"])
        self.assertEqual(payload["results"][0]["actual_routing"], "unknown")
        self.assertFalse(payload["results"][0]["routing_match"])
        self.assertNotIn("dummy", output_text)

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
    def test_runner_records_routing_metadata_and_redacts_secrets(self, chat):
        chat.return_value = {
            "answer": "Oberon is a Pretender.",
            "conversation_id": "conversation-1",
            "message_id": "message-1",
            "trace_status": "ok",
            "trace_source": "stream",
            "workflow_run_id": "workflow-1",
            "executed_nodes": [],
            "tool_invoked": True,
            "tool_name": "lookup_servant",
            "tool_input": {"servant_id": 42, "api_key": "[redacted]"},
            "tool_response_metadata": {"status": 200},
            "retrieval_used": False,
            "actual_routing": "servant_tool",
        }
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory, cases=[
                {
                    "id": "tool-route",
                    "category": "out_of_scope_structured_fact",
                    "question": "What is Oberon's class?",
                    "source": "servant tool",
                    "expected_facts": [],
                    "forbidden_claims": [],
                    "expected_routing": "servant_tool",
                }
            ])
            output = Path(directory) / "results.json"
            call_command("evaluate_agent", cases=str(cases), output=str(output))
            output_text = output.read_text(encoding="utf-8")
            result = json.loads(output_text)["results"][0]

        self.assertTrue(result["success"])
        self.assertTrue(result["tool_invoked"])
        self.assertEqual(result["tool_name"], "lookup_servant")
        self.assertEqual(result["tool_input"]["servant_id"], 42)
        self.assertEqual(result["tool_input"]["api_key"], "[redacted]")
        self.assertEqual(result["tool_response_metadata"], {"status": 200})
        self.assertFalse(result["retrieval_used"])
        self.assertEqual(result["actual_routing"], "servant_tool")
        self.assertTrue(result["routing_match"])
        self.assertNotIn("private-key", output_text)

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    def trace_from_message(self, message):
        with patch("apps.agent.management.commands.evaluate_agent.requests.get") as history_get:
            history_get.return_value.raise_for_status.return_value = None
            history_get.return_value.json.return_value = {"data": [message]}
            return evaluate_agent.fetch_dify_message_trace("conversation-1", "message-1")

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    def test_trace_classifies_tool_only_retrieval_only_both_and_neither(self):
        cases = [
            (
                {"agent_thoughts": [{"tool": "lookup_servant", "tool_input": "{}"}], "retriever_resources": []},
                "servant_tool",
            ),
            (
                {"agent_thoughts": [], "retriever_resources": [{"document_name": "combat"}]},
                "rag",
            ),
            (
                {"agent_thoughts": [{"tool": "lookup_servant", "tool_input": "{}"}], "retriever_resources": [{"document_name": "combat"}]},
                "both",
            ),
            (
                {"agent_thoughts": [], "retriever_resources": []},
                "none",
            ),
        ]

        for message, expected_routing in cases:
            with self.subTest(expected_routing=expected_routing):
                message["id"] = "message-1"
                trace = self.trace_from_message(message)
                self.assertEqual(trace["actual_routing"], expected_routing)
                self.assertEqual(trace["retrieval_used"], expected_routing in ("rag", "both"))

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    def test_trace_ignores_empty_tools_and_parses_multiple_thoughts(self):
        trace = self.trace_from_message(
            {
                "id": "message-1",
                "agent_thoughts": [
                    {"tool": "", "tool_input": "ignored"},
                    {"tool": "lookup_servant", "tool_input": '{"servant_id": 42}', "observation": {"status": 200}},
                    {"tool": "lookup_servant", "tool_input": "not-json", "observation": "safe observation"},
                ],
                "retriever_resources": [],
            }
        )

        self.assertTrue(trace["tool_invoked"])
        self.assertEqual(trace["tool_name"], ["lookup_servant", "lookup_servant"])
        self.assertEqual(trace["tool_input"][0], {"servant_id": 42})
        self.assertEqual(trace["tool_input"][1], "not-json")
        self.assertEqual(trace["tool_response_metadata"], [{"status": 200}, "safe observation"])

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    def test_trace_matches_exact_message_id_and_ignores_unrelated_history(self):
        with patch("apps.agent.management.commands.evaluate_agent.requests.get") as history_get:
            history_get.return_value.raise_for_status.return_value = None
            history_get.return_value.json.return_value = {
                "data": [
                    {"id": "other", "agent_thoughts": [{"tool": "wrong"}], "retriever_resources": [{"x": 1}]},
                    {"id": "message-1", "agent_thoughts": [], "retriever_resources": []},
                ]
            }
            trace = evaluate_agent.fetch_dify_message_trace("conversation-1", "message-1")

        self.assertEqual(trace["trace_status"], "ok")
        self.assertFalse(trace["tool_invoked"])
        self.assertEqual(trace["actual_routing"], "none")

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    def test_trace_unavailable_is_non_fatal_and_classifies_unknown(self):
        with patch(
            "apps.agent.management.commands.evaluate_agent.requests.get",
            side_effect=requests.RequestException("private history failure"),
        ):
            trace = evaluate_agent.fetch_dify_message_trace("conversation-1", "message-1")

        self.assertEqual(trace["trace_status"], "unavailable")
        self.assertEqual(trace["actual_routing"], "unknown")
        self.assertIsNone(trace["retrieval_used"])

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
    def test_stream_failure_records_controlled_error(self, chat):
        chat.side_effect = evaluate_agent.StreamingEvaluationError("private stream failure")
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory, cases=[
                {
                    "id": "trace-failure",
                    "category": "knowledge_hit",
                    "question": "question",
                    "source": "source",
                    "expected_facts": [],
                    "forbidden_claims": [],
                }
            ])
            output = Path(directory) / "results.json"
            call_command("evaluate_agent", cases=str(cases), output=str(output))
            result = json.loads(output.read_text(encoding="utf-8"))["results"][0]

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "agent_stream_error")
        self.assertEqual(result["actual_routing"], "unknown")
        self.assertFalse(result["routing_match"])

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.requests.post")
    def test_stream_reconstructs_answer_and_captures_structured_trace(self, post):
        events = [
            {"event": "ping", "data": {}},
            {"event": "workflow_started", "data": {"workflow_run_id": "workflow-1"}},
            {"event": "node_started", "data": {"id": "node-1", "node_type": "start", "title": "Start"}},
            {
                "event": "node_finished",
                "data": {
                    "id": "node-2",
                    "node_type": "agent",
                    "title": "Servant Agent",
                    "status": "succeeded",
                    "process_data": {
                        "tool_calls": [
                            {
                                "tool_name": "lookup_servant",
                                "input": '{"servant_id": 42}',
                                "output": {"status": 200},
                            }
                        ]
                    },
                    "outputs": {"answer": "partial"},
                    "execution_metadata": {"duration": 1},
                },
            },
            {"event": "message", "data": {"answer": "Oberon "}},
            {"event": "message", "data": {"answer": "is a Pretender."}},
            {"event": "not-json", "data": {}},
            {
                "event": "message_end",
                "data": {
                    "id": "message-1",
                    "conversation_id": "conversation-1",
                    "metadata": {"retriever_resources": []},
                },
            },
        ]
        response = Mock()
        response.iter_lines.return_value = [
            f"data: {json.dumps(event)}" for event in events[:6]
        ] + [
            "data: {broken",
            f"data: {json.dumps(events[-1])}",
        ]
        post.return_value = response

        result = evaluate_agent.stream_dify_chat("What is Oberon's class?")

        self.assertEqual(result["answer"], "Oberon is a Pretender.")
        self.assertEqual(result["message_id"], "message-1")
        self.assertEqual(result["conversation_id"], "conversation-1")
        self.assertEqual(result["workflow_run_id"], "workflow-1")
        self.assertEqual(result["trace_source"], "stream")
        self.assertEqual(len(result["executed_nodes"]), 2)
        self.assertTrue(result["tool_invoked"])
        self.assertEqual(result["tool_name"], "lookup_servant")
        self.assertEqual(result["tool_input"], {"servant_id": 42})
        self.assertEqual(result["tool_response_metadata"], {"status": 200})
        self.assertFalse(result["retrieval_used"])
        self.assertEqual(result["actual_routing"], "servant_tool")
        post.assert_called_once_with(
            "https://dify.example/v1/chat-messages",
            headers={
                "Authorization": "Bearer dummy",
                "Content-Type": "application/json",
            },
            json={
                "inputs": {},
                "query": "What is Oberon's class?",
                "response_mode": "streaming",
                "user": "chaldea-agent-dev",
            },
            timeout=30.0,
            stream=True,
        )

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.requests.post")
    def test_stream_classifies_retrieval_both_and_none(self, post):
        scenarios = [
            ([{"event": "node_finished", "data": {"node_type": "knowledge-retrieval", "outputs": {"documents": [1]}}}], [{"retriever_resources": [{"name": "combat"}]}], "rag"),
            ([{"event": "node_finished", "data": {"node_type": "knowledge-retrieval", "outputs": {"documents": [1]}}}, {"event": "node_finished", "data": {"node_type": "agent", "process_data": {"tool": "lookup_servant"}}}], [{"retriever_resources": [{"name": "combat"}]}], "both"),
            ([], [{"retriever_resources": []}], "none"),
        ]

        for nodes, end_metadata, expected in scenarios:
            with self.subTest(expected=expected):
                events = nodes + [{"event": "message", "data": {"answer": "answer"}}, {"event": "message_end", "data": {"id": "message-1", "conversation_id": "conversation-1", "metadata": end_metadata[0]}}]
                response = Mock()
                response.iter_lines.return_value = [f"data: {json.dumps(event)}" for event in events]
                post.return_value = response
                result = evaluate_agent.stream_dify_chat("question")
                self.assertEqual(result["actual_routing"], expected)

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.requests.post")
    def test_stream_errors_are_controlled(self, post):
        response = Mock()
        response.iter_lines.return_value = [
            'data: {"event": "error", "data": {"code": "secret", "message": "private"}}'
        ]
        post.return_value = response

        with self.assertRaisesRegex(evaluate_agent.StreamingEvaluationError, "reported an error"):
            evaluate_agent.stream_dify_chat("question")

        post.reset_mock()
        response.iter_lines.return_value = ['data: {"event": "message", "data": {"answer": "partial"}}']
        with self.assertRaisesRegex(evaluate_agent.StreamingEvaluationError, "before message_end"):
            evaluate_agent.stream_dify_chat("question")

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
    def test_invalid_expected_routing_fails_clearly(self, chat):
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory, cases=[
                {
                    "id": "invalid-route",
                    "category": "knowledge_hit",
                    "question": "question",
                    "source": "source",
                    "expected_facts": [],
                    "forbidden_claims": [],
                    "expected_routing": "guess",
                }
            ])
            output = Path(directory) / "results.json"

            with self.assertRaisesRegex(CommandError, "expected_routing"):
                call_command("evaluate_agent", cases=str(cases), output=str(output))

        chat.assert_not_called()

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
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
    @patch("apps.agent.management.commands.evaluate_agent.time.sleep")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
    def test_default_delay_is_zero(self, chat, sleep):
        chat.return_value = {
            "answer": "safe",
            "conversation_id": None,
            "message_id": None,
        }
        with TemporaryDirectory() as directory:
            cases = self.write_cases(
                directory,
                cases=[
                    {
                        "id": "one",
                        "category": "knowledge_hit",
                        "question": "one",
                        "source": "source",
                        "expected_facts": [],
                        "forbidden_claims": [],
                    },
                    {
                        "id": "two",
                        "category": "knowledge_hit",
                        "question": "two",
                        "source": "source",
                        "expected_facts": [],
                        "forbidden_claims": [],
                    },
                ],
            )
            output = Path(directory) / "results.json"
            call_command("evaluate_agent", cases=str(cases), output=str(output))

        sleep.assert_not_called()

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.time.sleep")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
    def test_custom_delay_sleeps_between_requests_not_after_final(self, chat, sleep):
        chat.return_value = {
            "answer": "safe",
            "conversation_id": None,
            "message_id": None,
        }
        with TemporaryDirectory() as directory:
            cases = self.write_cases(
                directory,
                cases=[
                    {
                        "id": "one",
                        "category": "knowledge_hit",
                        "question": "one",
                        "source": "source",
                        "expected_facts": [],
                        "forbidden_claims": [],
                    },
                    {
                        "id": "two",
                        "category": "knowledge_hit",
                        "question": "two",
                        "source": "source",
                        "expected_facts": [],
                        "forbidden_claims": [],
                    },
                    {
                        "id": "three",
                        "category": "knowledge_hit",
                        "question": "three",
                        "source": "source",
                        "expected_facts": [],
                        "forbidden_claims": [],
                    },
                ],
            )
            output = Path(directory) / "results.json"
            call_command(
                "evaluate_agent",
                cases=str(cases),
                output=str(output),
                delay_seconds=2.5,
            )

        self.assertEqual(sleep.call_args_list, [call(2.5), call(2.5)])

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
    def test_retrieval_flag_and_experiment_label_are_recorded(self, chat):
        chat.return_value = {
            "answer": "safe",
            "conversation_id": None,
            "message_id": None,
        }
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory, cases=[
                {
                    "id": "post-rag",
                    "category": "knowledge_hit",
                    "question": "question",
                    "source": "source",
                    "expected_facts": [],
                    "forbidden_claims": [],
                }
            ])
            output = Path(directory) / "results.json"
            call_command(
                "evaluate_agent",
                cases=str(cases),
                output=str(output),
                retrieval_used=True,
                experiment_label="post-rag-controlled",
            )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(payload["retrieval_used"])
        self.assertEqual(payload["experiment_label"], "post-rag-controlled")
        self.assertEqual(payload["results"][0]["status"], "success")

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
    def test_negative_delay_is_rejected(self, chat):
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory, cases=[
                {
                    "id": "negative-delay",
                    "category": "knowledge_hit",
                    "question": "question",
                    "source": "source",
                    "expected_facts": [],
                    "forbidden_claims": [],
                }
            ])
            output = Path(directory) / "results.json"

            with self.assertRaisesRegex(CommandError, "delay-seconds"):
                call_command(
                    "evaluate_agent",
                    cases=str(cases),
                    output=str(output),
                    delay_seconds=-1,
                )

        chat.assert_not_called()

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
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
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
    def test_missing_configuration_fails_before_evaluation(self, chat):
        with TemporaryDirectory() as directory:
            cases = self.write_cases(directory)
            output = Path(directory) / "results.json"

            with self.assertRaisesRegex(CommandError, "DIFY_API_BASE_URL"):
                call_command("evaluate_agent", cases=str(cases), output=str(output))

        chat.assert_not_called()

    @override_settings(DIFY_API_BASE_URL="https://dify.example/v1", DIFY_API_KEY="dummy")
    @patch("apps.agent.management.commands.evaluate_agent.stream_dify_chat")
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
