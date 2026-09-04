from django.http import JsonResponse
from django.shortcuts import render

import requests

from . import services


def index(request):
    return render(request, "servants/index.html", {"active_menu": "products"})


def detail(request, servant_id):
    return render(
        request,
        "servants/detail.html",
        {"active_menu": "products", "servant_id": servant_id},
    )


def servant_detail_api(request, servant_id):
    try:
        raw_servant = services.fetch_atlas_servant_detail(servant_id)
    except services.AtlasNotFoundError:
        return JsonResponse(
            {"ok": False, "message": "未找到指定的英灵资料"},
            status=404,
        )
    except requests.RequestException:
        return JsonResponse(
            {"ok": False, "message": "英灵资料加载失败，请稍后重试"},
            status=502,
        )
    except Exception:
        return JsonResponse(
            {"ok": False, "message": "英灵资料加载失败，请稍后重试"},
            status=502,
        )

    if not raw_servant:
        return JsonResponse(
            {"ok": False, "message": "未找到指定的英灵资料"},
            status=404,
        )

    return JsonResponse(
        {"ok": True, "servant": services.normalize_servant_detail(raw_servant)}
    )


def servants_api(request):
    class_name = request.GET.get("className", "All")
    search = (request.GET.get("search") or "").strip().lower()
    page = services.parse_positive_int(request.GET.get("page"), 1)
    limit = min(
        services.parse_positive_int(request.GET.get("limit"), services.MAX_LIMIT),
        services.MAX_LIMIT,
    )

    try:
        servants = services.fetch_servants(class_name)
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
