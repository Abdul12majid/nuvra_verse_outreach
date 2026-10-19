from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from .outreach import draft_outreach, queue_for_approval
from .services import approve_outreach, reject_outreach
from .models import OutreachChannel, SendStatus

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
    draft_preview = request.session.pop(f"draft_preview_{lead.pk}", None)

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
        "draft_preview": draft_preview,
        "channels": OutreachChannel.choices,
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



def lead_draft_outreach(request, pk):
    """
    Generate a draft for this lead. Shown as a preview on the lead detail page.
    If `commit=1` in POST, writes an OutreachLog in AWAITING_APPROVAL.
    """
    lead = get_object_or_404(Lead, pk=pk)
    if request.method != "POST":
        return redirect("core:lead_detail", pk=lead.pk)

    channel = request.POST.get("channel") or OutreachChannel.DISCORD_DM
    result = draft_outreach(
        lead,
        channel=channel,
        sender_name="Your Name",  # ← replace with a real setting later
        portfolio_url="https://your-portfolio.example",
    )

    if result.blocked_reason:
        messages.warning(request, f"Cannot draft: {result.blocked_reason}")
        return redirect("core:lead_detail", pk=lead.pk)

    if request.POST.get("commit") == "1":
        outreach = queue_for_approval(lead, result, channel=channel)
        messages.success(request, f"Draft queued for approval (#{outreach.pk}).")
        return redirect("core:lead_detail", pk=lead.pk)

    # Preview-only: stash in session and render the lead detail page with a preview panel.
    request.session[f"draft_preview_{lead.pk}"] = {
        "subject": result.subject,
        "body": result.body,
        "channel": channel,
    }
    return redirect("core:lead_detail", pk=lead.pk)


def approval_queue(request):
    """
    Every outreach in AWAITING_APPROVAL state, newest first.
    """
    items = (
        OutreachLog.objects
        .filter(status=SendStatus.AWAITING_APPROVAL)
        .select_related("lead", "signal")
        .order_by("-created_at")
    )
    return render(request, "core/approval_queue.html", {"items": items})


def approve_outreach_view(request, pk):
    outreach = get_object_or_404(OutreachLog, pk=pk)
    if request.method == "POST":
        approve_outreach(outreach)
        messages.success(request, "Approved.")
    return redirect(request.POST.get("next") or "core:approval_queue")


def reject_outreach_view(request, pk):
    outreach = get_object_or_404(OutreachLog, pk=pk)
    if request.method == "POST":
        reason = request.POST.get("reason", "")
        reject_outreach(outreach, reason)
        messages.success(request, "Rejected.")
    return redirect(request.POST.get("next") or "core:approval_queue")