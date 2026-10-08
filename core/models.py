# core/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Source(models.TextChoices):
    REDDIT = "reddit", "Reddit"
    DISCORD = "discord", "Discord"
    EMAIL = "email", "Email (scraped)"
    TAPAS = "tapas", "Tapas"
    WEBTOON = "webtoon", "Webtoon"
    BEHANCE = "behance", "Behance"
    ARTSTATION = "artstation", "ArtStation"
    GLOBALCOMIX = "globalcomix", "GlobalComix"
    FACEBOOK = "facebook", "Facebook"
    X = "x", "X / Twitter"
    INSTAGRAM = "instagram", "Instagram"
    OTHER = "other", "Other"


class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    QUALIFIED = "qualified", "Qualified"
    CONTACTED = "contacted", "Contacted"
    REPLIED = "replied", "Replied"
    NEGOTIATING = "negotiating", "Negotiating"
    WON = "won", "Won"
    LOST = "lost", "Lost"
    DISQUALIFIED = "disqualified", "Disqualified"


class SendMethod(models.TextChoices):
    AUTOMATED = "automated", "Automated"
    MANUAL = "manual", "Manual (human-approved)"
    HYBRID = "hybrid", "Hybrid (automated prep, manual send)"


class OutreachChannel(models.TextChoices):
    REDDIT_POST = "reddit_post", "Reddit post"
    REDDIT_COMMENT = "reddit_comment", "Reddit comment"
    REDDIT_DM = "reddit_dm", "Reddit DM"
    DISCORD_CHANNEL = "discord_channel", "Discord channel post"
    DISCORD_DM = "discord_dm", "Discord DM"
    EMAIL = "email", "Email"
    OTHER = "other", "Other"


class SendStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped (opt-out / rule block)"
    AWAITING_APPROVAL = "awaiting_approval", "Awaiting human approval"


class SignalType(models.TextChoices):
    # Behavior-derived signals. Add freely; the enum is just a vocabulary.
    NEW_PROJECT_LAUNCH = "new_project_launch", "New project launched"
    SCHEDULE_SLIPPING = "schedule_slipping", "Update schedule slipping"
    SOLO_CREATOR = "solo_creator", "Doing everything themselves"
    WRITER_NO_ARTIST = "writer_no_artist", "Writer / no artist attached"
    ART_FRUSTRATION = "art_frustration", "Frustration with art"
    SEEKING_COLLAB = "seeking_collab", "Mentions seeking collaborator"
    CROWDFUND_STRUGGLE = "crowdfund_struggle", "Crowdfunding underperforming"
    BIO_SEEKING_ARTIST = "bio_seeking_artist", "Bio says 'looking for artist'"
    ARTIST_INTEREST = "artist_interest", "Interacting with multiple artists"
    BETWEEN_PROJECTS = "between_projects", "Between projects / just finished"
    PUBLIC_LFA = "public_lfa", "Public 'looking for artist' post"
    OTHER = "other", "Other"


class SignalConfidence(models.IntegerChoices):
    LOW = 1, "Low"
    MEDIUM = 2, "Medium"
    HIGH = 3, "High"


class Lead(models.Model):
    """
    Unified lead record. Every platform app creates Leads here.
    Platform-specific fields go in raw_data; keep the shared fields generic.
    """
    source = models.CharField(max_length=32, choices=Source.choices, db_index=True)
    source_uid = models.CharField(max_length=255, db_index=True)
    source_url = models.URLField(blank=True)

    display_name = models.CharField(max_length=255, blank=True)
    headline = models.CharField(max_length=512, blank=True)
    bio = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=32, choices=LeadStatus.choices, default=LeadStatus.NEW, db_index=True
    )

    # Cached aggregate so the dashboard can sort without an N+1 across Signals.
    signal_score = models.IntegerField(default=0, db_index=True)
    signal_count = models.IntegerField(default=0)

    raw_data = models.JSONField(default=dict, blank=True)

    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("source", "source_uid")]
        indexes = [
            models.Index(fields=["source", "status"]),
            models.Index(fields=["-signal_score"]),
            models.Index(fields=["-last_seen_at"]),
        ]

    def __str__(self):
        return f"[{self.source}] {self.display_name or self.source_uid}"


class Signal(models.Model):
    """
    A detected indicator that a Lead may need an artist.
    Many Signals -> one Lead. Signals are append-only and timestamped.
    """
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="signals")
    source = models.CharField(max_length=32, choices=Source.choices, db_index=True)
    signal_type = models.CharField(max_length=32, choices=SignalType.choices, db_index=True)
    confidence = models.IntegerField(choices=SignalConfidence.choices, default=SignalConfidence.MEDIUM)

    # Points back to what was observed: a Reddit post, a profile, a comment, etc.
    source_url = models.URLField(blank=True)
    external_id = models.CharField(max_length=255, blank=True, db_index=True)

    # Short human-readable summary for the daily shortlist UI.
    summary = models.CharField(max_length=512, blank=True)
    # Evidence text / snippet that triggered the signal.
    evidence = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["signal_type", "-detected_at"]),
            models.Index(fields=["source", "-detected_at"]),
            models.Index(fields=["lead", "-detected_at"]),
        ]
        # Prevent duplicate signals from repeated scans of the same item.
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id", "signal_type"],
                name="uniq_signal_per_source_item_type",
                condition=models.Q(external_id__gt=""),
            )
        ]

    def __str__(self):
        return f"{self.signal_type} ({self.confidence}) -> lead {self.lead_id}"


class ContactMethod(models.Model):
    """
    A way to reach a Lead. One Lead can have several.
    Opt-outs are keyed by identifier (ContactPreference), not by Lead.
    """
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="contacts")
    channel = models.CharField(max_length=32, choices=OutreachChannel.choices)
    identifier = models.CharField(max_length=512, db_index=True)
    is_primary = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("lead", "channel", "identifier")]
        indexes = [models.Index(fields=["channel", "identifier"])]

    def __str__(self):
        return f"{self.channel}:{self.identifier}"


class ContactPreference(models.Model):
    """
    Global opt-out registry keyed by (channel, identifier).
    Survives across Leads so the same human isn't re-contacted via a new Lead row.
    """
    channel = models.CharField(max_length=32, choices=OutreachChannel.choices)
    identifier = models.CharField(max_length=512, db_index=True)
    opted_out = models.BooleanField(default=False)
    opted_out_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("channel", "identifier")]

    def __str__(self):
        return f"{self.channel}:{self.identifier} opt_out={self.opted_out}"


class OutreachLog(models.Model):
    """
    Append-only log of every outreach attempt (automated or manual).
    Source of truth for throttling and for response linkage.
    """
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="outreaches")
    contact = models.ForeignKey(
        ContactMethod, on_delete=models.SET_NULL, null=True, blank=True, related_name="outreaches"
    )
    # Optional link to the signal that prompted this outreach (for conversion analytics).
    signal = models.ForeignKey(
        Signal, on_delete=models.SET_NULL, null=True, blank=True, related_name="outreaches"
    )
    channel = models.CharField(max_length=32, choices=OutreachChannel.choices)
    send_method = models.CharField(max_length=16, choices=SendMethod.choices)

    subject = models.CharField(max_length=512, blank=True)
    body = models.TextField(blank=True)

    status = models.CharField(max_length=32, choices=SendStatus.choices, default=SendStatus.PENDING)
    error_message = models.TextField(blank=True)

    external_id = models.CharField(max_length=255, blank=True, db_index=True)
    external_url = models.URLField(blank=True)

    scheduled_for = models.DateTimeField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "scheduled_for"]),
            models.Index(fields=["channel", "sent_at"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.channel} {self.status} -> lead {self.lead_id}"


class Response(models.Model):
    """
    A reply received against a specific OutreachLog (or unattached).
    """
    outreach = models.ForeignKey(
        OutreachLog, on_delete=models.CASCADE, related_name="responses", null=True, blank=True
    )
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="responses")
    channel = models.CharField(max_length=32, choices=OutreachChannel.choices)
    external_id = models.CharField(max_length=255, blank=True, db_index=True)
    body = models.TextField(blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    is_positive = models.BooleanField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["lead", "-received_at"])]

    def __str__(self):
        return f"Response on outreach {self.outreach_id} for lead {self.lead_id}"


class SendQueue(models.Model):
    """
    Pending automated sends. Manual sends bypass this and write OutreachLog directly.
    Workers drain this respecting per-channel throttles.
    """
    outreach = models.OneToOneField(
        OutreachLog, on_delete=models.CASCADE, related_name="queue_entry"
    )
    run_after = models.DateTimeField(db_index=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["run_after", "locked_at"])]

    def __str__(self):
        return f"queue:{self.outreach_id} after {self.run_after}"