from django.shortcuts import render
from .models import Lead, Signal, OutreachLog, Response


def home(request):
    context = {
        "lead_count": Lead.objects.count(),
        "signal_count": Signal.objects.count(),
        "outreach_count": OutreachLog.objects.count(),
        "response_count": Response.objects.count(),
    }
    return render(request, "home.html", context)