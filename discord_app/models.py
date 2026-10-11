from django.db import models


class WatchedChannel(models.Model):
    guild_id = models.CharField(max_length=32, db_index=True)
    channel_id = models.CharField(max_length=32, unique=True)
    guild_name = models.CharField(max_length=255, blank=True)
    channel_name = models.CharField(max_length=255, blank=True)

    active = models.BooleanField(default=True, db_index=True)

    # personal/descriptive note
    note = models.CharField(max_length=255, blank=True)
    
    ignore_bots = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["guild_id", "active"])]

    def __str__(self):
        return f"{self.guild_name or self.guild_id} #{self.channel_name or self.channel_id}"