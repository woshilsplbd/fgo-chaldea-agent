from django.http import JsonResponse

from .services import MAX_LIMIT
from .services import fetch_servants
from .services import parse_positive_int


def servants_api(request):
    class_name = request.GET.get("className", "All")
    search = (request.GET.get("search") or "").strip().lower()
    page = parse_positive_int(request.GET.get("page"), 1)
    limit = min(parse_positive_int(request.GET.get("limit"), MAX_LIMIT), MAX_LIMIT)

    try:
        servants = fetch_servants(class_name)
    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "message": "英灵资料加载失败，请检查网络或 requests 依赖",
                "results": [],
            },
            status=502,
        )

    if search:
        servants = [
            servant
            for servant in servants
            if search in servant["name"].lower()
        ]

    servants.sort(key=lambda servant: int(servant["collectionNo"] or 0))

    total = len(servants)
    total_pages = max((total + limit - 1) // limit, 1)
    if page > total_pages:
        page = total_pages

    start = (page - 1) * limit
    end = start + limit

    return JsonResponse(
        {
            "ok": True,
            "results": servants[start:end],
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": total_pages,
            "hasPrev": page > 1,
            "hasNext": page < total_pages,
            "className": class_name,
            "search": search,
        }
    )
