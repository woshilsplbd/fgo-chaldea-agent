import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse


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
