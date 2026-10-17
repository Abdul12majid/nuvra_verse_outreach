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
        # --- Expanded PUBLIC_LFA patterns ---
    # Explicit requests for comic / manga / webtoon / webcomic artists.
    (
        re.compile(
            r"\b(?:looking for|need|seeking|searching for|want|hire|hiring)\b"
            r"[^.\n]{0,40}\b(?:comic|manga|webtoon|webcomic|comic book)\b"
            r"[^.\n]{0,20}\b(?:artist|illustrator|drawer)\b",
            re.I,
        ),
        SignalType.PUBLIC_LFA,
        SignalConfidence.HIGH,
        "Seeking a comic/manga/webtoon artist",
    ),
    (
        re.compile(
            r"\b(?:looking for|need|seeking|searching for|want|hire|hiring)\b"
            r"[^.\n]{0,40}\b(?:character designer|concept artist|cover artist|storyboard artist|"
            r"digital artist|illustrator|visual designer|logo designer|poster designer|"
            r"book cover designer|thumbnail designer|photoshop artist|album cover artist)\b",
            re.I,
        ),
        SignalType.PUBLIC_LFA,
        SignalConfidence.HIGH,
        "Seeking a specific type of artist",
    ),
    # "Need someone to draw / illustrate / design X".
    (
        re.compile(
            r"\b(?:need|want|looking for)\b[^.\n]{0,30}"
            r"\b(?:someone to|an? artist to|an? illustrator to)\b"
            r"[^.\n]{0,40}\b(?:draw|illustrate|design|bring .{0,20} to life|create)\b",
            re.I,
        ),
        SignalType.PUBLIC_LFA,
        SignalConfidence.HIGH,
        "Needs someone to draw/illustrate/design",
    ),
    # "Does anyone draw / anyone here who can draw / can someone illustrate".
    (
        re.compile(
            r"\b(?:any(?:one)?|anybody|someone|any artists?)\b"
            r"[^.\n]{0,20}\b(?:here )?(?:who can |that can |available|interested in )?"
            r"(?:draw|illustrate|design|do commissions|do character art)\b",
            re.I,
        ),
        SignalType.PUBLIC_LFA,
        SignalConfidence.MEDIUM,
        "Asking if anyone can draw/illustrate/commission",
    ),
    # "Who can draw this / who does character art / does anyone do commissions".
    (
        re.compile(
            r"\b(?:who can (?:draw|illustrate)|who does (?:character art|commissions)|"
            r"does anyone (?:do commissions|draw|take commissions))\b",
            re.I,
        ),
        SignalType.PUBLIC_LFA,
        SignalConfidence.HIGH,
        "Directly soliciting art services",
    ),
    # "I have a project/idea that needs an artist".
    (
        re.compile(
            r"\b(?:i have|i've got)\b[^.\n]{0,40}\b(?:project|comic|idea|story|series)\b"
            r"[^.\n]{0,40}\b(?:need(?:s)?|looking for|requires?)\b[^.\n]{0,20}\b(?:artist|illustrator|art)\b",
            re.I,
        ),
        SignalType.PUBLIC_LFA,
        SignalConfidence.HIGH,
        "Project with stated need for an artist",
    ),
    # "I need help with the visuals / need someone with drawing skills".
    (
        re.compile(
            r"\b(?:need help with (?:the )?visuals|need someone with drawing skills|"
            r"need an? (?:artist|illustrator) (?:asap|urgently|right away))\b",
            re.I,
        ),
        SignalType.PUBLIC_LFA,
        SignalConfidence.HIGH,
        "Needs visual / drawing help (incl. urgent)",
    ),

    # --- Explicit SEEKING_COLLAB patterns ---
    # Partnership-framed requests: "art partner", "regular artist", "team", "long-term".
    (
        re.compile(
            r"\b(?:looking for|seeking|want|need)\b[^.\n]{0,40}"
            r"\b(?:art partner|regular artist|long[- ]term (?:collaboration|artist|partner)|"
            r"art(?:ist)? team|team of artists|artists to join|"
            r"ongoing (?:project|collaboration|artist))\b",
            re.I,
        ),
        SignalType.SEEKING_COLLAB,
        SignalConfidence.HIGH,
        "Seeking a partnership / long-term / team collaboration",
    ),
    # "Artist for multiple projects / upcoming series / upcoming project".
    (
        re.compile(
            r"\b(?:artist|illustrator)\b[^.\n]{0,40}"
            r"\b(?:for (?:multiple|several|upcoming|next) (?:projects?|series|comic|webtoon))\b",
            re.I,
        ),
        SignalType.SEEKING_COLLAB,
        SignalConfidence.HIGH,
        "Artist needed for upcoming / multiple projects",
    ),

    # --- BUDGET_SIGNAL patterns (new signal type) ---
    # Any mention of pay, rates, budget, per-page pricing, paid position.
    (
        re.compile(
            r"\b(?:budget (?:is|of|around)|paying \$|\$\d+ ?(?:per|/|a) ?(?:page|illustration|piece|image)|"
            r"rate per (?:page|illustration)|\$\d+|paid (?:per|position|freelance|work)|"
            r"seeking a paid artist|artist budget|commission budget|payment upfront|"
            r"paying well|competitive pay|paid gig)\b",
            re.I,
        ),
        SignalType.BUDGET_SIGNAL,
        SignalConfidence.HIGH,
        "Mentions budget / pay / rates",
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