from django.shortcuts import render


def chat(request):
    return render(request, "agent/chat.html", {"active_menu": "agent"})
