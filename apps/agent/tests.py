from django.test import TestCase
from django.urls import reverse


class AgentChatPageTests(TestCase):
    def test_agent_page_renders_without_backend_request(self):
        response = self.client.get(reverse("agent:chat"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agent/chat.html")
        self.assertContains(response, 'id="agent-chat"')
        self.assertContains(response, "迦勒底智能终端")
        self.assertContains(response, "Chaldea Agent")
        self.assertContains(response, "尚未连接")

    def test_agent_navigation_points_to_agent_page(self):
        response = self.client.get(reverse("agent:chat"))

        self.assertContains(response, 'id="agent"')
        self.assertContains(response, 'href="/agent/"')

    def test_agent_page_has_no_backend_endpoint_or_fake_response(self):
        response = self.client.get(reverse("agent:chat"))

        self.assertNotContains(response, "/api/agent/chat/")
        self.assertNotContains(response, "assistant-message")
