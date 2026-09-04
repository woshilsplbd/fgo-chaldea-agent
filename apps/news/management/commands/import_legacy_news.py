import json
from datetime import timezone as datetime_timezone
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.news.models import NewsArticle


REQUIRED_FIELDS = {
    "id",
    "title",
    "description",
    "newType",
    "publishDate",
    "views",
}


def parse_publish_date(value, row_number):
    if not isinstance(value, str):
        raise CommandError(
            f"row {row_number}: publishDate must be an ISO datetime string"
        )
    parsed = parse_datetime(value)
    if parsed is None:
        raise CommandError(f"row {row_number}: invalid publishDate")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    return parsed


class Command(BaseCommand):
    help = "Import preserved legacy news records into V2 NewsArticle rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            required=True,
            help="Path to the UTF-8 legacy news preservation JSON file.",
        )

    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.is_file():
            raise CommandError(f"source JSON does not exist: {source}")

        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            raise CommandError("source JSON must be UTF-8") from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"invalid JSON: {exc.msg}") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
            raise CommandError("source JSON must contain a top-level rows list")
        if payload.get("source_table") != "newsApp_mynew":
            raise CommandError("source JSON must come from newsApp_mynew")

        created_count = 0
        updated_count = 0
        with transaction.atomic():
            for row_number, row in enumerate(payload["rows"], start=1):
                if not isinstance(row, dict):
                    raise CommandError(f"row {row_number}: expected an object")
                missing = REQUIRED_FIELDS.difference(row)
                if missing:
                    names = ", ".join(sorted(missing))
                    raise CommandError(f"row {row_number}: missing fields: {names}")

                legacy_id = row["id"]
                if isinstance(legacy_id, bool) or not isinstance(legacy_id, int):
                    raise CommandError(f"row {row_number}: id must be an integer")
                if not isinstance(row["title"], str):
                    raise CommandError(f"row {row_number}: title must be a string")
                if not isinstance(row["description"], str):
                    raise CommandError(
                        f"row {row_number}: description must be a string"
                    )
                if not isinstance(row["newType"], str):
                    raise CommandError(f"row {row_number}: newType must be a string")
                if isinstance(row["views"], bool) or not isinstance(row["views"], int):
                    raise CommandError(f"row {row_number}: views must be an integer")

                _, created = NewsArticle.objects.update_or_create(
                    pk=legacy_id,
                    defaults={
                        "title": row["title"],
                        "description": row["description"],
                        "news_type": row["newType"],
                        "publish_date": parse_publish_date(row["publishDate"], row_number),
                        "views": row["views"],
                    },
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(payload['rows'])} records "
                f"(created={created_count}, updated={updated_count})."
            )
        )
