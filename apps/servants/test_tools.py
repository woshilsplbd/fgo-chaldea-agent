import json
from unittest.mock import patch

import requests
from django.test import Client, TestCase, override_settings


class ServantToolApiTests(TestCase):
    url = "/api/tools/servant/"
    token = "tool-test-token"

    def post(self, payload=None, token=None, body=None, client=None):
        if body is None:
            body = json.dumps(payload)
        client = client or self.client
        extra = {}
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return client.post(
            self.url,
            data=body,
            content_type="application/json",
            **extra,
        )

    @staticmethod
    def detail_payload():
        return {
            "id": 42,
            "collectionNo": 42,
            "name": "Oberon",
            "className": "pretender",
            "rarity": 5,
            "skills": [
                {
                    "name": "Dreamlike Charisma",
                    "rank": "EX",
                    "icon": "https://example.test/skill.png",
                    "detail": "A skill",
                }
            ],
            "noblePhantasms": [
                {
                    "name": "Endless Fairy Tale",
                    "rank": "EX",
                    "card": "Buster",
                    "detail": "A Noble Phantasm",
                }
            ],
            "extraAssets": {
                "faces": {"ascension": {"stage1": "https://example.test/face.png"}}
            },
            "profile": {"comments": [{"comment": "Private profile"}]},
        }

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail")
    def test_id_lookup_returns_compact_normalized_success(self, fetch_detail):
        fetch_detail.return_value = self.detail_payload()

        response = self.post({"servant_id": 42}, token=self.token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()["servant"]),
            {
                "id",
                "collectionNo",
                "name",
                "className",
                "displayClassName",
                "rarity",
                "rarityStars",
                "skills",
                "noblePhantasms",
            },
        )
        self.assertEqual(response.json()["servant"]["name"], "Oberon")
        self.assertNotIn("https://example.test", response.content.decode())
        self.assertNotIn("Private profile", response.content.decode())
        fetch_detail.assert_called_once_with(42)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail")
    def test_id_lookup_ignores_empty_optional_name_values(self, fetch_detail):
        fetch_detail.return_value = self.detail_payload()

        for empty_name in (None, "", "   "):
            with self.subTest(empty_name=empty_name):
                fetch_detail.reset_mock()
                response = self.post(
                    {"servant_id": 42, "name": empty_name},
                    token=self.token,
                )

                self.assertEqual(response.status_code, 200)
                fetch_detail.assert_called_once_with(42)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail")
    @patch("apps.servants.tool_views.services.fetch_atlas_servants_by_name")
    def test_name_lookup_ignores_empty_optional_id_values(self, fetch_servants, fetch_detail):
        fetch_servants.return_value = [
            {"id": 42, "collectionNo": 42, "name": "Oberon", "className": "pretender", "rarity": 5}
        ]
        fetch_detail.return_value = self.detail_payload()

        for empty_id in (None, "", "   "):
            with self.subTest(empty_id=empty_id):
                fetch_servants.reset_mock()
                fetch_detail.reset_mock()
                response = self.post(
                    {"servant_id": empty_id, "name": " Oberon "},
                    token=self.token,
                )

                self.assertEqual(response.status_code, 200)
                fetch_servants.assert_called_once_with("Oberon")
                fetch_detail.assert_called_once_with(42)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail")
    @patch("apps.servants.tool_views.services.fetch_atlas_servants_by_name")
    def test_name_lookup_is_trimmed_and_exact_case_insensitive(self, fetch_servants, fetch_detail):
        fetch_servants.return_value = [
            {
                "id": 42,
                "collectionNo": 42,
                "name": "Oberon",
                "className": "pretender",
                "rarity": 5,
            }
        ]
        fetch_detail.return_value = self.detail_payload()

        response = self.post({"name": "  oberon  "}, token=self.token)

        self.assertEqual(response.status_code, 200)
        fetch_servants.assert_called_once_with("oberon")
        fetch_detail.assert_called_once_with(42)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_missing_selector_returns_400(self):
        response = self.post({}, token=self.token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_only_empty_selectors_return_400(self):
        response = self.post({"servant_id": None, "name": ""}, token=self.token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_both_selectors_return_400(self):
        response = self.post({"servant_id": 42, "name": "Oberon"}, token=self.token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_invalid_servant_id_returns_400(self):
        for value in (0, -1, "42", "abc", True, None):
            with self.subTest(value=value):
                response = self.post({"servant_id": value}, token=self.token)
                self.assertEqual(response.status_code, 400)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_empty_or_overlong_name_returns_400(self):
        for value in (" ", "x" * 201):
            with self.subTest(value=value):
                response = self.post({"name": value}, token=self.token)
                self.assertEqual(response.status_code, 400)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_non_string_name_returns_400(self):
        response = self.post({"name": 42}, token=self.token)
        self.assertEqual(response.status_code, 400)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_malformed_json_returns_400(self):
        response = self.post(token=self.token, body="{broken")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_unknown_fields_are_rejected(self):
        response = self.post({"name": "Oberon", "className": "pretender"}, token=self.token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail", return_value={})
    def test_id_not_found_returns_404(self, fetch_detail):
        response = self.post({"servant_id": 999}, token=self.token)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "servant_not_found")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servants_by_name")
    def test_name_not_found_returns_404(self, fetch_servants):
        fetch_servants.return_value = []
        response = self.post({"name": "Unknown"}, token=self.token)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "servant_not_found")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servants_by_name")
    def test_ambiguous_name_returns_409_with_compact_candidates(self, fetch_servants):
        fetch_servants.return_value = [
            {"id": 1, "name": "Artoria Alter", "className": "saber", "rarity": 5, "skills": []},
            {"id": 2, "name": "Artoria Lily", "className": "saber", "rarity": 4, "skills": []},
        ]

        response = self.post({"name": "Artoria"}, token=self.token)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "ambiguous_servant")
        self.assertEqual(
            set(response.json()["candidates"][0]),
            {"id", "name", "className", "rarity"},
        )
        self.assertNotIn("skills", response.content.decode())

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servants_by_name")
    def test_name_search_upstream_failure_returns_502(self, fetch_servants):
        fetch_servants.side_effect = requests.RequestException("private upstream search")

        response = self.post({"name": "Oberon"}, token=self.token)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "servant_upstream_error")
        self.assertNotIn("private upstream search", response.content.decode())

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail")
    def test_upstream_failure_returns_502_without_details(self, fetch_detail):
        fetch_detail.side_effect = requests.RequestException("private upstream body")
        response = self.post({"servant_id": 42}, token=self.token)
        body = response.content.decode()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "servant_upstream_error")
        self.assertNotIn("private upstream body", body)
        self.assertNotIn("RequestException", body)
        self.assertNotIn("Traceback", body)

    @override_settings(AGENT_TOOL_API_TOKEN="")
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail")
    def test_missing_configuration_returns_503(self, fetch_detail):
        response = self.post({"servant_id": 42}, token=self.token)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "tool_not_configured")
        fetch_detail.assert_not_called()

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_missing_authorization_returns_401(self):
        response = self.post({"servant_id": 42})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "unauthorized")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_invalid_authorization_returns_401(self):
        for authorization in ("Bearer wrong", "Basic tool-test-token", "Bearer"):
            with self.subTest(authorization=authorization):
                response = self.client.post(
                    self.url,
                    data=json.dumps({"servant_id": 42}),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=authorization,
                )
                self.assertEqual(response.status_code, 401)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail", return_value={})
    def test_valid_bearer_token_allows_request_and_is_not_returned(self, fetch_detail):
        response = self.post({"servant_id": 42}, token=self.token)
        body = response.content.decode()

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.token, body)
        fetch_detail.assert_called_once_with(42)

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    def test_unsupported_method_returns_controlled_405(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["code"], "method_not_allowed")

    @override_settings(AGENT_TOOL_API_TOKEN=token)
    @patch("apps.servants.tool_views.services.fetch_atlas_servant_detail")
    def test_machine_endpoint_is_csrf_exempt_with_valid_bearer(self, fetch_detail):
        fetch_detail.return_value = self.detail_payload()
        client = Client(enforce_csrf_checks=True)

        response = self.post({"servant_id": 42}, token=self.token, client=client)

        self.assertEqual(response.status_code, 200)
