from unittest.mock import patch

import requests
from django.test import TestCase

from . import services


class ServantsApiTests(TestCase):
    def setUp(self):
        services._servant_cache.clear()
        services._servant_detail_cache.clear()

    def tearDown(self):
        services._servant_cache.clear()
        services._servant_detail_cache.clear()

    @staticmethod
    def atlas_payload():
        return [
            {
                "id": 1,
                "collectionNo": 1,
                "name": "Artoria",
                "className": "saber",
                "rarity": 5,
                "extraAssets": {
                    "faces": {"ascension": {"stage1": "https://example.test/face.png"}}
                },
            },
            {
                "id": 2,
                "collectionNo": 2,
                "originalName": "Emiya",
                "classType": {"id": "archer", "name": "archer"},
                "rarity": 4,
            },
            {
                "id": 1,
                "collectionNo": 1,
                "name": "Artoria (duplicate)",
                "className": "saber",
                "rarity": 5,
            },
        ]

    @patch("apps.servants.services.request_atlas")
    def test_normal_get_returns_success_contract(self, request_atlas):
        request_atlas.return_value = self.atlas_payload()

        response = self.client.get("/api/servants/?className=saber")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                "ok",
                "results",
                "page",
                "limit",
                "total",
                "totalPages",
                "hasPrev",
                "hasNext",
                "className",
                "search",
            },
            set(data),
        )
        self.assertEqual(data["className"], "saber")
        self.assertEqual(data["total"], 2)
        self.assertEqual([item["collectionNo"] for item in data["results"]], [1, 2])

    @patch("apps.servants.services.request_atlas")
    def test_pagination_and_search_metadata(self, request_atlas):
        request_atlas.return_value = self.atlas_payload()

        response = self.client.get("/api/servants/?className=saber&page=2&limit=1")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["limit"], 1)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["totalPages"], 2)
        self.assertTrue(data["hasPrev"])
        self.assertFalse(data["hasNext"])
        self.assertEqual(data["search"], "")
        self.assertEqual(data["results"][0]["collectionNo"], 2)

    @patch("apps.servants.services.request_atlas")
    def test_limit_is_bounded_and_invalid_values_use_default(self, request_atlas):
        request_atlas.return_value = self.atlas_payload()

        excessive = self.client.get("/api/servants/?className=saber&limit=999")
        invalid = self.client.get("/api/servants/?className=saber&limit=invalid")

        self.assertEqual(excessive.json()["limit"], services.MAX_LIMIT)
        self.assertEqual(invalid.json()["limit"], services.MAX_LIMIT)

    @patch("apps.servants.services.request_atlas")
    def test_upstream_failure_returns_controlled_502(self, request_atlas):
        request_atlas.side_effect = requests.RequestException("upstream secret")

        response = self.client.get("/api/servants/?className=saber")
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(response.json()["results"], [])
        self.assertNotIn("upstream secret", body)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("RequestException", body)

    def test_representative_atlas_payload_is_normalized(self):
        servant = services.normalize_servant(
            {
                "id": 42,
                "name": "Mash",
                "className": {"id": "shielder", "name": "shielder"},
                "rarity": "4",
                "extraAssets": {
                    "faces": {"ascension": {"stage1": "https://example.test/mash.png"}}
                },
            }
        )

        self.assertEqual(servant["id"], 42)
        self.assertEqual(servant["className"], "shielder")
        self.assertEqual(servant["displayClassName"], "Shielder")
        self.assertEqual(servant["rarity"], 4)
        self.assertEqual(servant["rarityStars"], "★★★★")
        self.assertEqual(servant["face"], "https://example.test/mash.png")
        self.assertEqual(servant["image"], servant["face"])
