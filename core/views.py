from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from .models import Lead, Signal, LeadStatus, Source, SignalType, OutreachLog, Response


def _paginate(request, queryset, per_page=25):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page") or 1
    return paginator.get_page(page_number)


def dashboard(request):
    """
    Top-level summary. Counts plus the highest-signal leads right now.
    """
    top_leads = (
        Lead.objects
        .annotate(num_signals=Count("signals"))
        .filter(num_signals__gt=0)
        .order_by("-signal_score", "-last_seen_at")[:10]
    )

    recent_signals = Signal.objects.select_related("lead").order_by("-detected_at")[:10]

    context = {
        "lead_count": Lead.objects.count(),
        "signal_count": Signal.objects.count(),
        "outreach_count": OutreachLog.objects.count(),
        "response_count": Response.objects.count(),
        "top_leads": top_leads,
        "recent_signals": recent_signals,
    }
    return render(request, "core/dashboard.html", context)


def lead_list(request):
    """
    Filterable, paginated list of leads.
    Filters: source, status, has_signals, q (search).
    """
    qs = Lead.objects.all().order_by("-signal_score", "-last_seen_at")

    source = request.GET.get("source")
    status = request.GET.get("status")
    has_signals = request.GET.get("has_signals")
    q = request.GET.get("q", "").strip()

    if source:
        qs = qs.filter(source=source)
    if status:
        qs = qs.filter(status=status)
    if has_signals == "1":
        qs = qs.filter(signal_count__gt=0)
    if q:
        qs = qs.filter(
            Q(display_name__icontains=q)
            | Q(headline__icontains=q)
            | Q(bio__icontains=q)
            | Q(source_uid__icontains=q)
        )

    page = _paginate(request, qs, per_page=25)

    context = {
        "page": page,
        "sources": Source.choices,
        "statuses": LeadStatus.choices,
        "current_source": source or "",
        "current_status": status or "",
        "current_has_signals": has_signals or "",
        "q": q,
    }
    return render(request, "core/lead_list.html", context)


def lead_detail(request, pk):
    """
    One lead: profile, signals, outreach history, responses.
    Allows status change and marking outreach as contacted manually.
    """
    lead = get_object_or_404(Lead, pk=pk)
    signals = lead.signals.order_by("-detected_at")
    outreaches = lead.outreaches.order_by("-created_at")
    responses = lead.responses.order_by("-received_at")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "set_status":
            new_status = request.POST.get("status")
            if new_status in dict(LeadStatus.choices):
                lead.status = new_status
                lead.save(update_fields=["status", "updated_at"])
                messages.success(request, f"Status set to {lead.get_status_display()}.")
            return redirect("core:lead_detail", pk=lead.pk)

    context = {
        "lead": lead,
        "signals": signals,
        "outreaches": outreaches,
        "responses": responses,
        "statuses": LeadStatus.choices,
        "username": (lead.raw_data or {}).get("username", ""),
    }
    return render(request, "core/lead_detail.html", context)


def signal_list(request):
    """
    Filterable, paginated list of every signal across every platform.
    Filters: source, signal_type, confidence, q (search over summary/evidence).
    """
    qs = Signal.objects.select_related("lead").order_by("-detected_at")

    source = request.GET.get("source")
    signal_type = request.GET.get("signal_type")
    q = request.GET.get("q", "").strip()

    if source:
        qs = qs.filter(source=source)
    if signal_type:
        qs = qs.filter(signal_type=signal_type)
    if q:
        qs = qs.filter(Q(summary__icontains=q) | Q(evidence__icontains=q))

    page = _paginate(request, qs, per_page=50)

    context = {
        "page": page,
        "sources": Source.choices,
        "signal_types": SignalType.choices,
        "current_source": source or "",
        "current_signal_type": signal_type or "",
        "q": q,
    }
    return render(request, "core/signal_list.html", context)