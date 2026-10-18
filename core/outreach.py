from dataclasses import dataclass
from django.utils import timezone

from .models import (
    Lead, Signal, OutreachLog, ContactPreference,
    Source, OutreachChannel, SendMethod, SendStatus, SignalType,
)


@dataclass
class DraftResult:
    subject: str
    body: str
    signal: Signal | None
    blocked_reason: str = ""


# Per-signal-type opening lines. The draft picks the highest-confidence signal
# and uses its opening. Add freely.
_OPENINGS = {
    SignalType.PUBLIC_LFA: "Saw your post about needing an artist",
    SignalType.SEEKING_COLLAB: "Saw you're looking for a collaborator",
    SignalType.WRITER_NO_ARTIST: "Noticed you're writing without an artist attached",
    SignalType.SOLO_CREATOR: "Noticed you're handling everything yourself",
    SignalType.ART_FRUSTRATION: "Noticed you've mentioned struggling with the art side",
    SignalType.NEW_PROJECT_LAUNCH: "Congrats on the new project launch",
    SignalType.SCHEDULE_SLIPPING: "Saw you've been dealing with some schedule slips",
    SignalType.CROWDFUND_STRUGGLE: "Saw the crowdfunding campaign is in progress",
    SignalType.BETWEEN_PROJECTS: "Saw you just wrapped a project",
    SignalType.BIO_SEEKING_ARTIST: "Saw your profile mentions looking for an artist",
    SignalType.ARTIST_INTEREST: "Noticed you've been engaging with comic artists",
    SignalType.BUDGET_SIGNAL: "Saw you're budgeting for art",
    SignalType.OTHER: "Reached out because I think we could work well together",
}

_BODY_TEMPLATE = """{opening} — {context}

I'm a comic/webtoon artist and I do character art, pages, and covers. If it's useful, here's a quick look at what I've done: {portfolio_url}

Happy to talk through what you're working on, no pressure either way. If you'd rather not hear from me again, just reply "no thanks" and I'll take you off my list.

— {sender_name}"""


def _context_for(signal: Signal) -> str:
    """Turn a signal's evidence into a short quoted context phrase."""
    if signal.evidence:
        # Trim to a short quoted fragment.
        snippet = signal.evidence.strip()
        if len(snippet) > 100:
            snippet = snippet[:97].rstrip() + "..."
        return f'you said: "{snippet}"'
    return ""


def _best_signal(lead: Lead) -> Signal | None:
    """
    Pick the signal that best justifies outreach: highest confidence,
    most recent as tiebreak.
    """
    return lead.signals.order_by("-confidence", "-detected_at").first()


def _already_contacted(lead: Lead) -> bool:
    return lead.outreaches.filter(
        status__in=[SendStatus.SENT, SendStatus.PENDING, SendStatus.AWAITING_APPROVAL]
    ).exists()


def _opted_out(lead: Lead, channel: str) -> bool:
    """Check ContactPreference for any identifier attached to this lead."""
    identifiers = list(lead.contacts.values_list("identifier", flat=True))
    if not identifiers:
        return False
    return ContactPreference.objects.filter(
        channel=channel, identifier__in=identifiers, opted_out=True
    ).exists()


def draft_outreach(
    lead: Lead,
    *,
    channel: str,
    sender_name: str,
    portfolio_url: str,
) -> DraftResult:
    """
    Build a personalized first-message draft for a lead.

    Does NOT create an OutreachLog — the caller decides whether to create
    the log (approval queue) or discard the draft.
    """
    if _already_contacted(lead):
        return DraftResult("", "", None, blocked_reason="Already has outreach pending or sent.")

    if _opted_out(lead, channel):
        return DraftResult("", "", None, blocked_reason="Lead has opted out on this channel.")

    signal = _best_signal(lead)
    if signal is None:
        return DraftResult("", "", None, blocked_reason="Lead has no signals to reference.")

    opening = _OPENINGS.get(signal.signal_type, _OPENINGS[SignalType.OTHER])
    context = _context_for(signal)

    subject = "Quick question about your project"
    body = _BODY_TEMPLATE.format(
        opening=opening,
        context=context,
        portfolio_url=portfolio_url,
        sender_name=sender_name,
    )
    return DraftResult(subject=subject, body=body, signal=signal)


def queue_for_approval(
    lead: Lead,
    draft: DraftResult,
    *,
    channel: str,
    contact_identifier: str = "",
) -> OutreachLog:
    """
    Create an OutreachLog in AWAITING_APPROVAL state, linked to the signal
    the draft references. Human approves or rejects later.
    """
    contact = lead.contacts.filter(identifier=contact_identifier).first() if contact_identifier else None

    return OutreachLog.objects.create(
        lead=lead,
        contact=contact,
        signal=draft.signal,
        channel=channel,
        send_method=SendMethod.MANUAL,  # default; caller can flip to AUTOMATED
        subject=draft.subject,
        body=draft.body,
        status=SendStatus.AWAITING_APPROVAL,
    )