# discord_app/management/commands/discord_ping.py
import asyncio
import discord
from django.core.management.base import BaseCommand, CommandError
from discord_app.client import build_client, get_token, DiscordConfigError


class Command(BaseCommand):
    help = (
        "Smoke-test Discord bot credentials. Logs the bot in, prints its "
        "identity, and lists every server (guild) it is a member of. "
        "Writes nothing to the database and posts nothing to Discord."
    )

    def handle(self, *args, **options):
        try:
            token = get_token()
        except DiscordConfigError as e:
            raise CommandError(str(e))

        client = build_client()

        @client.event
        async def on_ready():
            try:
                self.stdout.write(self.style.SUCCESS(
                    f"Logged in as: {client.user} (id={client.user.id})"
                ))
                guilds = list(client.guilds)
                if not guilds:
                    self.stdout.write(self.style.WARNING(
                        "Bot is not a member of any servers. "
                        "Use the OAuth2 URL from the Developer Portal to invite it."
                    ))
                else:
                    self.stdout.write(f"Member of {len(guilds)} server(s):\n")
                    for g in guilds:
                        self.stdout.write(
                            f"  - {g.name}  (id={g.id})  members={g.member_count}"
                        )
                self.stdout.write(self.style.SUCCESS("Discord smoke test OK."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error during on_ready: {e}"))
            finally:
                await client.close()

        try:
            asyncio.run(client.start(token, reconnect=False))
        except discord.LoginFailure:
            raise CommandError(
                "Discord rejected the token (LoginFailure). "
                "Reset the token in the Developer Portal and update .env."
            )
        except discord.PrivilegedIntentsRequired:
            raise CommandError(
                "Bot is missing a privileged intent. Enable 'Message Content Intent' "
                "and 'Server Members Intent' on the Bot page of the Developer Portal."
            )
        except Exception as e:
            raise CommandError(f"Unexpected error connecting to Discord: {e}")