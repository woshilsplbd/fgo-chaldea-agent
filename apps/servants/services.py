import time

import requests


ATLAS_SERVANT_SEARCH_URL = "https://api.atlasacademy.io/nice/JP/servant/search"
ATLAS_SERVANT_DETAIL_URL = "https://api.atlasacademy.io/nice/JP/servant/{}"
MAX_LIMIT = 30
CACHE_SECONDS = 600

BASIC_CLASS_NAMES = (
    "saber",
    "archer",
    "lancer",
    "rider",
    "caster",
    "assassin",
    "berserker",
)
EXTRA_CLASS_NAMES = (
    "shielder",
    "ruler",
    "avenger",
    "moonCancer",
    "alterEgo",
    "foreigner",
    "pretender",
    "beast",
)
ALL_CLASS_NAMES = BASIC_CLASS_NAMES + EXTRA_CLASS_NAMES
CLASS_ALIASES = {
    "all": "all",
    "saber": "saber",
    "archer": "archer",
    "lancer": "lancer",
    "rider": "rider",
    "caster": "caster",
    "assassin": "assassin",
    "berserker": "berserker",
    "extra": "extra",
}

_servant_cache = {}
_servant_detail_cache = {}
_servant_name_cache = {}


class AtlasNotFoundError(Exception):
    """The upstream service has no servant for the requested identifier."""


def display_class_name(class_name):
    names = {
        "moonCancer": "Moon Cancer",
        "alterEgo": "Alter Ego",
        "shielder": "Shielder",
        "ruler": "Ruler",
        "avenger": "Avenger",
        "foreigner": "Foreigner",
        "pretender": "Pretender",
        "beast": "Beast",
    }
    if not class_name:
        return "Unknown"
    return names.get(class_name, class_name[:1].upper() + class_name[1:])


def find_first_image(value):
    if isinstance(value, str) and value.startswith("http"):
        return value
    if isinstance(value, list):
        for item in value:
            image = find_first_image(item)
            if image:
                return image
    if isinstance(value, dict):
        for item in value.values():
            image = find_first_image(item)
            if image:
                return image
    return ""


def request_atlas(class_name=None, *, name=None):
    params = {}
    if class_name is not None:
        params["className"] = class_name
    if name is not None:
        params["name"] = name
    response = requests.get(
        ATLAS_SERVANT_SEARCH_URL,
        params=params,
        timeout=8,
    )
    response.raise_for_status()
    return response.json()


def request_atlas_detail(servant_id):
    detail_url = ATLAS_SERVANT_DETAIL_URL.format(servant_id)
    response = requests.get(detail_url, params={"lore": "true"}, timeout=8)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        if response.status_code == 404:
            raise AtlasNotFoundError from exc
        raise
    return response.json()


def fetch_atlas_servants_by_class(class_name):
    now = time.time()
    cached = _servant_cache.get(class_name)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["data"]

    data = request_atlas(class_name)
    if not isinstance(data, list):
        data = []

    _servant_cache[class_name] = {"time": now, "data": data}
    return data


def fetch_atlas_servants_by_name(name):
    normalized_name = (name or "").strip()
    cache_key = normalized_name.casefold()
    now = time.time()
    cached = _servant_name_cache.get(cache_key)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["data"]

    raw_servants = request_atlas(name=normalized_name)
    if not isinstance(raw_servants, list):
        raw_servants = []

    servants_by_id = {}
    for servant in raw_servants:
        if not isinstance(servant, dict):
            continue
        servant_id = servant.get("collectionNo") or servant.get("id")
        if servant_id:
            servants_by_id[servant_id] = servant

    data = [normalize_servant(servant) for servant in servants_by_id.values()]
    _servant_name_cache[cache_key] = {"time": now, "data": data}
    return data


def fetch_atlas_servant_detail(servant_id):
    now = time.time()
    cached = _servant_detail_cache.get(servant_id)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["data"]

    data = request_atlas_detail(servant_id)
    if not isinstance(data, dict):
        data = {}

    _servant_detail_cache[servant_id] = {"time": now, "data": data}
    return data


def requested_classes(class_name):
    normalized = CLASS_ALIASES.get((class_name or "all").strip().lower(), "all")
    if normalized == "all":
        return ALL_CLASS_NAMES
    if normalized == "extra":
        return EXTRA_CLASS_NAMES
    return (normalized,)


def servant_image(servant):
    extra_assets = servant.get("extraAssets") or {}

    image = find_first_image(extra_assets.get("faces") or {})
    if image:
        return image

    for key in ("face", "image", "icon", "thumbnail"):
        image = find_first_image(servant.get(key))
        if image:
            return image

    return find_first_image(extra_assets.get("image") or {})


def servant_large_image(servant):
    extra_assets = servant.get("extraAssets") or {}
    chara_graph = extra_assets.get("charaGraph") or {}
    ascension = chara_graph.get("ascension") if isinstance(chara_graph, dict) else {}

    if isinstance(ascension, dict):
        for key in sorted(ascension.keys(), reverse=True):
            image = find_first_image(ascension.get(key))
            if image:
                return image

    for key in ("charaGraph", "charaFigure", "image"):
        image = find_first_image(extra_assets.get(key) or {})
        if image:
            return image

    return servant_image(servant)


def normalize_servant(servant):
    class_name = servant.get("className") or servant.get("classType") or ""
    if isinstance(class_name, dict):
        class_name = class_name.get("name") or class_name.get("id") or ""

    rarity = servant.get("rarity") or 0
    try:
        rarity = int(rarity)
    except (TypeError, ValueError):
        rarity = 0

    image = servant_image(servant)
    return {
        "id": servant.get("id") or "",
        "name": servant.get("name") or servant.get("originalName") or "",
        "className": class_name,
        "classType": class_name,
        "displayClassName": display_class_name(class_name),
        "rarity": rarity,
        "rarityStars": "★" * rarity if rarity else "未记录",
        "face": image,
        "image": image,
        "collectionNo": servant.get("collectionNo") or servant.get("id") or "",
    }


def normalize_servant_detail(servant):
    summary = normalize_servant(servant)
    summary.update(
        {
            "largeImage": servant_large_image(servant),
            "noblePhantasms": normalize_noble_phantasms(servant),
            "skills": normalize_skills(servant),
            "description": servant_description(servant),
        }
    )
    return summary


def servant_description(servant):
    profile = servant.get("profile") or {}
    comments = profile.get("comments") if isinstance(profile, dict) else []
    if isinstance(comments, list):
        for item in comments:
            comment = item.get("comment") if isinstance(item, dict) else ""
            if comment:
                return comment
    return "暂无简介。"


def normalize_noble_phantasms(servant):
    noble_phantasms = servant.get("noblePhantasms") or []
    results = []
    for noble_phantasm in noble_phantasms:
        if not isinstance(noble_phantasm, dict):
            continue
        results.append(
            {
                "name": noble_phantasm.get("name")
                or noble_phantasm.get("originalName")
                or "未记录",
                "rank": noble_phantasm.get("rank") or "未记录",
                "card": noble_phantasm.get("card") or "",
                "detail": noble_phantasm.get("detail")
                or noble_phantasm.get("unmodifiedDetail")
                or "",
            }
        )
    return results


def normalize_skills(servant):
    skills = servant.get("skills") or []
    results = []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        results.append(
            {
                "name": skill.get("name") or skill.get("originalName") or "未记录",
                "rank": skill.get("rank") or "未记录",
                "icon": skill.get("icon") or "",
                "detail": skill.get("detail") or "",
            }
        )
    return results


def parse_positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def fetch_servants(class_name):
    raw_servants = []
    for atlas_class in requested_classes(class_name):
        raw_servants.extend(fetch_atlas_servants_by_class(atlas_class))

    servants_by_id = {}
    for servant in raw_servants:
        if not isinstance(servant, dict):
            continue
        servant_id = servant.get("collectionNo") or servant.get("id")
        if servant_id:
            servants_by_id[servant_id] = servant

    return [normalize_servant(servant) for servant in servants_by_id.values()]
