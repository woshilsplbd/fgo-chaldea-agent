import json
import secrets

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from . import services


MAX_NAME_LENGTH = 200
TOOL_FIELDS = {"servant_id", "name"}


def _error(code, message, status, **extra):
    payload = {"ok": False, "code": code, "message": message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _configured_token():
    return getattr(settings, "AGENT_TOOL_API_TOKEN", "") or ""


def _authorized(request, configured_token):
    authorization = request.META.get("HTTP_AUTHORIZATION", "")
    scheme, separator, token = authorization.partition(" ")
    return (
        separator
        and scheme.lower() == "bearer"
        and token
        and secrets.compare_digest(token, configured_token)
    )


def _compact_candidate(servant):
    return {
        "id": servant.get("id"),
        "name": servant.get("name", ""),
        "className": servant.get("className", ""),
        "rarity": servant.get("rarity", 0),
    }


def _compact_detail(detail):
    normalized = services.normalize_servant_detail(detail)
    return {
        "id": normalized.get("id"),
        "collectionNo": normalized.get("collectionNo"),
        "name": normalized.get("name", ""),
        "className": normalized.get("className", ""),
        "displayClassName": normalized.get("displayClassName", ""),
        "rarity": normalized.get("rarity", 0),
        "rarityStars": normalized.get("rarityStars", ""),
        "skills": [
            {
                "name": skill.get("name", ""),
                "rank": skill.get("rank", ""),
                "detail": skill.get("detail", ""),
            }
            for skill in normalized.get("skills", [])
            if isinstance(skill, dict)
        ],
        "noblePhantasms": [
            {
                "name": noble_phantasm.get("name", ""),
                "rank": noble_phantasm.get("rank", ""),
                "card": noble_phantasm.get("card", ""),
                "detail": noble_phantasm.get("detail", ""),
            }
            for noble_phantasm in normalized.get("noblePhantasms", [])
            if isinstance(noble_phantasm, dict)
        ],
    }


def _name_matches(name):
    servants = services.fetch_servants("all")
    normalized_name = name.casefold()
    exact = [
        servant
        for servant in servants
        if str(servant.get("name", "")).strip().casefold() == normalized_name
    ]
    if exact:
        return exact

    return [
        servant
        for servant in servants
        if normalized_name in str(servant.get("name", "")).casefold()
    ]


def _lookup_detail(servant_id):
    detail = services.fetch_atlas_servant_detail(servant_id)
    if not detail:
        return None
    return _compact_detail(detail)


@csrf_exempt  # Machine-to-machine Bearer auth replaces cookie-based CSRF here.
def servant_tool(request):
    """Authenticated, read-only Agent lookup boundary for structured Servant data."""
    if request.method != "POST":
        return _error("method_not_allowed", "Method not allowed.", 405)

    configured_token = _configured_token()
    if not configured_token:
        return _error(
            "tool_not_configured",
            "Servant tool is not configured.",
            503,
        )
    if not _authorized(request, configured_token):
        return _error("unauthorized", "Unauthorized.", 401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error("invalid_request", "Invalid request.", 400)

    if not isinstance(payload, dict) or set(payload) - TOOL_FIELDS:
        return _error("invalid_request", "Invalid request.", 400)

    has_id = "servant_id" in payload
    has_name = "name" in payload
    if has_id == has_name:
        return _error("invalid_request", "Provide exactly one lookup selector.", 400)

    if has_id:
        servant_id = payload["servant_id"]
        if isinstance(servant_id, bool) or not isinstance(servant_id, int) or servant_id <= 0:
            return _error("invalid_request", "servant_id must be a positive integer.", 400)
    else:
        name = payload["name"]
        if not isinstance(name, str):
            return _error("invalid_request", "name must be a non-empty string.", 400)
        name = name.strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            return _error("invalid_request", "name must be a non-empty string.", 400)

    try:
        if has_id:
            servant = _lookup_detail(servant_id)
            if servant is None:
                return _error("servant_not_found", "Servant not found.", 404)
        else:
            matches = _name_matches(name)
            if not matches:
                return _error("servant_not_found", "Servant not found.", 404)
            if len(matches) > 1:
                return _error(
                    "ambiguous_servant",
                    "Multiple servants match this name.",
                    409,
                    candidates=[_compact_candidate(item) for item in matches],
                )
            candidate_id = matches[0].get("id") or matches[0].get("collectionNo")
            servant = _lookup_detail(candidate_id)
            if servant is None:
                return _error("servant_not_found", "Servant not found.", 404)
    except services.AtlasNotFoundError:
        return _error("servant_not_found", "Servant not found.", 404)
    except requests.RequestException:
        return _error("servant_upstream_error", "Servant lookup failed.", 502)
    except Exception:
        return _error("servant_upstream_error", "Servant lookup failed.", 502)

    return JsonResponse({"ok": True, "servant": servant})
