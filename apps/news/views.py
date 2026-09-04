from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .models import NewsArticle


def index(request):
    query = (request.GET.get("q") or "").strip()
    articles = NewsArticle.objects.all()
    if query:
        articles = articles.filter(title__icontains=query)

    return render(
        request,
        "news/index.html",
        {"active_menu": "news", "articles": articles, "query": query},
    )


def detail(request, article_id):
    article = get_object_or_404(NewsArticle, pk=article_id)
    NewsArticle.objects.filter(pk=article_id).update(views=F("views") + 1)
    article.refresh_from_db()
    return render(
        request,
        "news/detail.html",
        {"active_menu": "news", "article": article},
    )
