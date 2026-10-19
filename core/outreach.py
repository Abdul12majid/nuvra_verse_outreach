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


# Per-signal opening lines. No quotes, no evidence — just a warm acknowledgment.
_OPENINGS = {
    SignalType.PUBLIC_LFA:         "Saw you're looking for an artist for your comic — I might be a good fit.",
    SignalType.SEEKING_COLLAB:     "Saw you're looking for a collaborator — reaching out because I think we'd work well together.",
    SignalType.WRITER_NO_ARTIST:   "I saw you're writing a comic and haven't locked in an artist yet — that's exactly the stage I like to come in at.",
    SignalType.SOLO_CREATOR:       "Saw you're doing everything yourself right now — figured I'd reach out in case you're open to sharing the workload.",
    SignalType.ART_FRUSTRATION:    "Saw you mentioned the art side has been frustrating — that's the kind of thing I help with.",
    SignalType.NEW_PROJECT_LAUNCH: "Congrats on the new launch — reaching out in case you're planning the next project and want an artist attached early.",
    SignalType.SCHEDULE_SLIPPING:  "Saw your update schedule has been slipping — a lot of that is usually art load. Reaching out in case you're considering bringing someone on.",
    SignalType.CROWDFUND_STRUGGLE: "Saw your crowdfunding campaign is running — reaching out in case you're thinking about art for the campaign or the book.",
    SignalType.BETWEEN_PROJECTS:   "Saw you just wrapped a project — reaching out in case you're lining up the next one.",
    SignalType.BIO_SEEKING_ARTIST: "Saw your profile mentions looking for an artist — figured I'd say hi.",
    SignalType.ARTIST_INTEREST:    "Noticed you've been following and commenting on comic artists — reaching out in case you're thinking about a project of your own.",
    SignalType.BUDGET_SIGNAL:      "Saw you're budgeting for art on your comic — reaching out because that's the kind of work I take on.",
    SignalType.OTHER:              "Reaching out because I think we might work well together on a comic project.",
}

# Body template with a real personalization slot. The human must fill {their_work}.
_BODY_TEMPLATE = """{opening}

{their_work}

A bit about me: I'm a comic/webtoon artist — character art, interior pages, and covers. Portfolio here: {portfolio_url}

If it's interesting, happy to talk through scope, timeline, and rates. If not, no worries at all.

— {sender_name}

(P.S. If you'd rather not hear from me again, just reply "no thanks" and I'll take you off my list.)"""


def draft_outreach(
    lead: Lead,
    *,
    channel: str,
    sender_name: str,
    portfolio_url: str,
) -> DraftResult:
    """
    Build a personalized first-message draft.

    The signal is used to select the opening line — it is NEVER quoted back
    at the recipient. The `{their_work}` slot is a placeholder that must be
    filled in by the human reviewer before sending; this is what makes the
    message feel human rather than templated.
    """
    if _already_contacted(lead):
        return DraftResult("", "", None, blocked_reason="Already has outreach pending or sent.")

    if _opted_out(lead, channel):
        return DraftResult("", "", None, blocked_reason="Lead has opted out on this channel.")

    signal = _best_signal(lead)
    if signal is None:
        return DraftResult("", "", None, blocked_reason="Lead has no signals to reference.")

    opening = _OPENINGS.get(signal.signal_type, _OPENINGS[SignalType.OTHER])

    subject = f"About your comic — quick question"
    body = _BODY_TEMPLATE.format(
        opening=opening,
        their_work="[Replace this line with ONE specific sentence about their project — the title, "
                   "the premise, a character, or something they said. This is the whole point. "
                   "If you can't fill this in, don't send the message.]",
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