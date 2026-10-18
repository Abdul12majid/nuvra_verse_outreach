# core/services.py
from django.db import transaction
from django.utils import timezone
from .models import Lead, Signal, Source, SignalType, SignalConfidence


@transaction.atomic
def upsert_lead(
    *,
    source: str,
    source_uid: str,
    display_name: str = "",
    headline: str = "",
    bio: str = "",
    source_url: str = "",
    raw_data: dict | None = None,
) -> Lead:
    """
    Get-or-create a Lead keyed by (source, source_uid).
    On existing leads, fills in blanks and updates last_seen_at.
    Does NOT overwrite a field with an empty string if it already has a value.
    """
    lead, created = Lead.objects.get_or_create(
        source=source,
        source_uid=source_uid,
        defaults={
            "display_name": display_name,
            "headline": headline,
            "bio": bio,
            "source_url": source_url,
            "raw_data": raw_data or {},
            "first_seen_at": timezone.now(),
            "last_seen_at": timezone.now(),
        },
    )
    if not created:
        # Fill blanks only — never clobber user-edited fields with empty values.
        if display_name and not lead.display_name:
            lead.display_name = display_name
        if headline and not lead.headline:
            lead.headline = headline
        if bio and not lead.bio:
            lead.bio = bio
        if source_url and not lead.source_url:
            lead.source_url = source_url
        if raw_data:
            lead.raw_data = {**(lead.raw_data or {}), **raw_data}
        lead.last_seen_at = timezone.now()
        lead.save(update_fields=[
            "display_name", "headline", "bio", "source_url",
            "raw_data", "last_seen_at", "updated_at",
        ])
    return lead


@transaction.atomic
def record_signal(
    *,
    lead: Lead,
    source: str,
    signal_type: str,
    summary: str = "",
    evidence: str = "",
    source_url: str = "",
    external_id: str = "",
    confidence: int = SignalConfidence.MEDIUM,
    raw_data: dict | None = None,
) -> tuple[Signal, bool]:
    """
    Create a Signal attached to a Lead, or return the existing one if the
    (source, external_id, signal_type) triple already exists.

    Updates cached aggregates on the Lead:
      - signal_count   = number of signals
      - signal_score   = sum of confidence values (LOW=1, MEDIUM=2, HIGH=3)

    Returns (signal, created).
    """
    signal, created = Signal.objects.get_or_create(
        source=source,
        external_id=external_id,
        signal_type=signal_type,
        defaults={
            "lead": lead,
            "confidence": confidence,
            "summary": summary,
            "evidence": evidence,
            "source_url": source_url,
            "raw_data": raw_data or {},
            "detected_at": timezone.now(),
        },
    )

    if created:
        # Recompute aggregates from the source of truth (cheap at prototype scale).
        agg_count = lead.signals.count()
        agg_score = sum(s.confidence for s in lead.signals.all())
        lead.signal_count = agg_count
        lead.signal_score = agg_score
        lead.save(update_fields=["signal_count", "signal_score", "updated_at"])

    return signal, created


@transaction.atomic
def approve_outreach(outreach) -> None:
    """
    Human has approved an outreach. Currently this only marks it SENT for
    manual channels. Automated channels will be wired in Stage 6.

    For manual channels, "approval" means the human will send it themselves
    outside the system — we record it as SENT so the audit trail is accurate.
    """
    from .models import SendStatus
    outreach.status = SendStatus.SENT
    outreach.sent_at = timezone.now()
    outreach.save(update_fields=["status", "sent_at", "updated_at"])


@transaction.atomic
def reject_outreach(outreach, reason: str = "") -> None:
    from .models import SendStatus
    outreach.status = SendStatus.SKIPPED
    outreach.error_message = reason or "Rejected by human reviewer"
    outreach.save(update_fields=["status", "error_message", "updated_at"])