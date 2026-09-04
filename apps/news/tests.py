import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import NewsArticle


class NewsArticleTests(TestCase):
    def test_news_article_stores_preserved_unicode_and_description_losslessly(self):
        description = "<p>玛修与マシュ的记录</p>\n第二行"
        article = NewsArticle.objects.create(
            title="奏章Ⅱ",
            description=description,
            news_type="主线剧情",
            publish_date="2026-05-17T22:28:02Z",
            views=3,
        )

        saved = NewsArticle.objects.get(pk=article.pk)
        self.assertEqual(saved.title, "奏章Ⅱ")
        self.assertEqual(saved.description, description)
        self.assertEqual(saved.news_type, "主线剧情")
        self.assertEqual(saved.views, 3)

    def write_source(self, rows):
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "news.json"
        path.write_text(
            json.dumps(
                {"source_table": "newsApp_mynew", "rows": rows},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def sample_rows():
        return [
            {
                "id": 12,
                "title": "第二道奏章",
                "description": "<p>废弃孔的记录</p>",
                "newType": "主线剧情",
                "publishDate": "2026-05-17 22:28:02",
                "views": 0,
            },
            {
                "id": 18,
                "title": "召唤公告",
                "description": "日文テキスト",
                "newType": "召唤公告",
                "publishDate": "2026-05-17T22:28:02+00:00",
                "views": 4,
            },
        ]

    def run_import(self, rows):
        output = StringIO()
        call_command(
            "import_legacy_news",
            source=str(self.write_source(rows)),
            stdout=output,
        )
        return output.getvalue()

    def test_import_preserves_ids_and_all_field_mappings(self):
        output = self.run_import(self.sample_rows())

        self.assertIn("created=2", output)
        self.assertEqual(set(NewsArticle.objects.values_list("pk", flat=True)), {12, 18})
        article = NewsArticle.objects.get(pk=12)
        self.assertEqual(article.title, "第二道奏章")
        self.assertEqual(article.description, "<p>废弃孔的记录</p>")
        self.assertEqual(article.news_type, "主线剧情")
        self.assertEqual(article.views, 0)

    def test_import_is_idempotent_and_updates_existing_ids(self):
        rows = self.sample_rows()
        self.run_import(rows)
        rows[0]["title"] = "第二道奏章（更新）"
        rows[0]["description"] = "更新后的内容"

        output = self.run_import(rows)

        self.assertIn("created=0", output)
        self.assertIn("updated=2", output)
        self.assertEqual(NewsArticle.objects.count(), 2)
        self.assertEqual(NewsArticle.objects.get(pk=12).title, "第二道奏章（更新）")
        self.assertEqual(NewsArticle.objects.get(pk=12).description, "更新后的内容")

    def test_malformed_json_fails_clearly(self):
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "broken.json"
        path.write_text("{not json", encoding="utf-8")

        with self.assertRaisesRegex(CommandError, "invalid JSON"):
            call_command("import_legacy_news", source=str(path))

    def test_missing_required_field_fails_clearly(self):
        rows = self.sample_rows()
        del rows[0]["description"]

        with self.assertRaisesRegex(CommandError, "missing fields: description"):
            self.run_import(rows)
