from django.db import models


class NewsArticle(models.Model):
    NEWS_TYPE_CHOICES = (
        ("主线剧情", "主线剧情"),
        ("限时活动", "限时活动"),
        ("召唤公告", "召唤公告"),
    )

    title = models.CharField(max_length=50)
    description = models.TextField(default="")
    news_type = models.CharField(max_length=50, choices=NEWS_TYPE_CHOICES)
    publish_date = models.DateTimeField()
    views = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-publish_date"]

    def __str__(self):
        return self.title
