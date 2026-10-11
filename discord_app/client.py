# discord_app/client.py
import os
import discord
from dotenv import load_dotenv

load_dotenv()


class DiscordConfigError(RuntimeError):
    """Raised when required Discord configuration is missing from the environment."""


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise DiscordConfigError(
            f"Missing required environment variable: {name}. "
            f"Set it in .env (see discord_app/client.py for the list)."
        )
    return value


def build_intents() -> discord.Intents:
    """
    Intents declare which categories of Discord events the bot receives.

    message_content is required for signal detection (reading message text).
    members is required for member-join events and permission checks in later stages.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    return intents


def build_client() -> discord.Client:
    """
    Build a discord.Client configured with the required intents.
    Does NOT connect. Caller is responsible for client.run() / client.start()
    with the token from get_token(), or for using it in a management command
    that manages the event loop itself.
    """
    return discord.Client(intents=build_intents())


def get_token() -> str:
    return _required_env("DISCORD_BOT_TOKEN")