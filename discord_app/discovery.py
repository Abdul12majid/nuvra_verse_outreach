import re
from dataclasses import dataclass
from core.models import SignalType, SignalConfidence


@dataclass
class SignalMatch:
    signal_type: str
    confidence: int
    summary: str
    evidence: str


# Each rule is a (compiled_pattern, signal_type, confidence, summary) tuple.
# Evidence = the matching snippet. Confidence is fixed per rule for now;
# later we can promote to context-sensitive scoring.

_RULES: list[tuple[re.Pattern, str, int, str]] = [
    # Explicit — highest confidence
    (
        re.compile(r"\blooking for (an? )?(artist|illustrator|comic artist)\b", re.I),
        SignalType.PUBLIC_LFA,
        SignalConfidence.HIGH,
        "Explicitly looking for an artist",
    ),
    (
        re.compile(r"\b(hiring|need|seeking|want)\b[^.\n]{0,40}\b(artist|illustrator)\b", re.I),
        SignalType.PUBLIC_LFA,
        SignalConfidence.HIGH,
        "Stated a need for an artist",
    ),
    (
        re.compile(r"\b(looking for|need|want)\b[^.\n]{0,40}\b(collab|collaborator|partner)\b", re.I),
        SignalType.SEEKING_COLLAB,
        SignalConfidence.HIGH,
        "Looking for a collaborator",
    ),

    # Writer without art — medium confidence
    (
        re.compile(r"\b(writer|writing|script|story)\b[^.\n]{0,60}\b(no art|no artist|without art|need art)\b", re.I),
        SignalType.WRITER_NO_ARTIST,
        SignalConfidence.HIGH,
        "Writer mentioning no artist attached",
    ),
    (
        re.compile(r"\b(i (am|'m) a writer|i write)\b", re.I),
        SignalType.WRITER_NO_ARTIST,
        SignalConfidence.MEDIUM,
        "Self-described writer",
    ),

    # Solo creator — doing it all themselves
    (
        re.compile(r"\b(i (do|draw|write)\b[^.\n]{0,40}\b(everything|all (of )?(it|this)))\b", re.I),
        SignalType.SOLO_CREATOR,
        SignalConfidence.HIGH,
        "Doing everything themselves",
    ),
    (
        re.compile(r"\b(solo|by myself|on my own|one[- ]man|one[- ]person)\b", re.I),
        SignalType.SOLO_CREATOR,
        SignalConfidence.MEDIUM,
        "Solo project mention",
    ),

    # Art frustration
    (
        re.compile(r"\b(i (can'?t|cannot|suck at) draw|my art (is|isn'?t|sucks)|art (is )?(my )?(weak(ness)?|weak point))\b", re.I),
        SignalType.ART_FRUSTRATION,
        SignalConfidence.HIGH,
        "Frustration with own art",
    ),

    # New project launch
    (
        re.compile(r"\b(just (launched|started|published|released)|launching|debut(ing)?)\b", re.I),
        SignalType.NEW_PROJECT_LAUNCH,
        SignalConfidence.MEDIUM,
        "Mentions a new project",
    ),

    # Schedule slipping (very rough — refine once we see real data)
    (
        re.compile(r"\b(sorry|apologies)\b[^.\n]{0,60}\b(late|delay|miss(ed)?|hiatus|behind schedule)\b", re.I),
        SignalType.SCHEDULE_SLIPPING,
        SignalConfidence.MEDIUM,
        "Mentions delays",
    ),

    # Crowdfunding
    (
        re.compile(r"\b(kickstarter|indiegogo|patreon|crowdfund(ing)?)\b", re.I),
        SignalType.CROWDFUND_STRUGGLE,
        SignalConfidence.LOW,
        "Mentions crowdfunding",
    ),
]


def detect_signals(message_text: str) -> list[SignalMatch]:
    """
    Run all rules against a message. Returns one SignalMatch per matched rule.
    A single message can produce multiple signals.
    """
    if not message_text or len(message_text.strip()) < 10:
        return []

    matches: list[SignalMatch] = []
    for pattern, signal_type, confidence, summary in _RULES:
        m = pattern.search(message_text)
        if m:
            # Grab a small window around the match as evidence.
            start = max(0, m.start() - 40)
            end = min(len(message_text), m.end() + 40)
            evidence = message_text[start:end].strip().replace("\n", " ")
            matches.append(SignalMatch(
                signal_type=signal_type,
                confidence=confidence,
                summary=summary,
                evidence=evidence,
            ))
    return matches