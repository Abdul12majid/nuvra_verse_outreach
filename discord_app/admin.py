from django.contrib import admin
from .models import WatchedChannel


@admin.register(WatchedChannel)
class WatchedChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "guild_name", "channel_name", "guild_id", "channel_id", "active", "note")
    list_filter = ("active", "guild_id")
    search_fields = ("guild_name", "channel_name", "channel_id", "note")