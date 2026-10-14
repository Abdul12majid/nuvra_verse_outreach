# discord_app/management/commands/discord_listen.py
import asyncio
import discord
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from discord_app.client import build_client, get_token, DiscordConfigError
from discord_app.models import WatchedChannel
from discord_app.discovery import detect_signals
from core.models import Source
from core.services import upsert_lead, record_signal


class Command(BaseCommand):
    help = (
        "Run the Discord listener. Connects the bot, reads messages from all "
        "active WatchedChannels, runs signal detection, and writes Leads + "
        "Signals. Runs until Ctrl-C."
    )

    def handle(self, *args, **options):
        try:
            token = get_token()
        except DiscordConfigError as e:
            raise CommandError(str(e))

        watched = list(
            WatchedChannel.objects.filter(active=True).values_list("channel_id", flat=True)
        )
        if not watched:
            raise CommandError(
                "No active WatchedChannels. Add one in the admin first "
                "(Discord → Watched channels), or create one from this command's output "
                "after listing channels."
            )

        watched_set = set(watched)
        self.stdout.write(self.style.SUCCESS(
            f"Watching {len(watched_set)} channel(s). Ctrl-C to stop."
        ))

        client = build_client()

        @client.event
        async def on_ready():
            self.stdout.write(self.style.SUCCESS(
                f"Listener online as {client.user} (id={client.user.id})"
            ))

        @client.event
        async def on_message(message: discord.Message):
            if message.author.bot:
                return  # skip bots
            if str(message.channel.id) not in watched_set:
                return

            text = message.content or ""
            matches = detect_signals(text)
            if not matches:
                return

            # Run DB writes in a thread to avoid blocking the event loop.
            await asyncio.to_thread(self._persist, message, matches)

        try:
            asyncio.run(client.start(token, reconnect=True))
        except KeyboardInterrupt:
            self.stdout.write("\nShutting down listener.")
        except discord.LoginFailure:
            raise CommandError("Discord rejected the token. Reset it in the Developer Portal.")
        except Exception as e:
            raise CommandError(f"Listener crashed: {e}")

    # ---- sync helpers (run in a worker thread) ----

    def _persist(self, message: discord.Message, matches) -> None:
        guild = message.guild
        author = message.author

        lead = upsert_lead(
            source=Source.DISCORD,
            source_uid=str(author.id),
            display_name=str(author),
            source_url=f"https://discord.com/users/{author.id}",
            raw_data={
                "username": author.name,
                "display_name": author.display_name,
                "discriminator": getattr(author, "discriminator", "0"),
                "guild_id": str(guild.id) if guild else "",
                "guild_name": guild.name if guild else "",
                "channel_id": str(message.channel.id),
                "channel_name": getattr(message.channel, "name", ""),
            },
        )

        signal_url = (
            f"https://discord.com/channels/{guild.id}/{message.channel.id}/{message.id}"
            if guild else ""
        )

        for match in matches:
            signal, created = record_signal(
                lead=lead,
                source=Source.DISCORD,
                signal_type=match.signal_type,
                summary=match.summary,
                evidence=match.evidence,
                source_url=signal_url,
                external_id=str(message.id),
                confidence=match.confidence,
                raw_data={
                    "message_id": str(message.id),
                    "channel_id": str(message.channel.id),
                    "guild_id": str(guild.id) if guild else "",
                    "author_id": str(author.id),
                },
            )
            flag = "NEW" if created else "dup"
            self.stdout.write(
                f"  [{flag}] {match.signal_type} "
                f"from {author} in #{getattr(message.channel, 'name', '?')}"
            )