import asyncio
import discord
from typing import Optional
from discord.ext import commands
from config import ONBOARDING_TIMEOUT_SECONDS, MAX_ONBOARDING_ATTEMPTS
from utils.persistence import (
    get_onboarding_enabled,
    set_onboarding_enabled,
    save_data,
)

class MessengerCog(commands.Cog):
    """Cog responsible for messaging new members in DMs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.onboarding_enabled = get_onboarding_enabled()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """DM anyone who joins the server."""
        # Ignore bots joining
        if member.bot:
            return
        
        if not self.onboarding_enabled:
            return

        try:
            await member.send(
                ":wave: Hey! Welcome to the server.\n\n"
                "I'm the bot that helps with GitHub + notifications. "
                "Before we get started — what's your **GitHub username**?\n"
                "Just reply to this DM with your username (no @ needed)."
            )

            def check(message: discord.Message) -> bool:
                return (
                    message.author.id == member.id and isinstance(message.channel, discord.DMChannel)
                )
            
            try:
                reply: discord.Message = await self.bot.wait_for("message", check=check, timeout=ONBOARDING_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                # No reply from user - remove from server
                try:
                    await member.send(
                        ":hourglass: Hey! You didn’t respond with your GitHub username, "
                        "so I have to remove you from the server for now.\n"
                        "Feel free to rejoin anytime!"
                    )
                except discord.Forbidden:
                    # They had DMs closed; still kick them
                    pass

                # Attempt to kick them
                try:
                    await member.kick(reason="Failed onboarding: no GitHub username provided.")
                    print(f"[MessengerCog] Kicked {member} ({member.id}) for timeout.")
                except Exception as e:
                    print(f"[MessengerCog] Failed to kick {member} ({member.id}): {e}")

                return
            
            for attempt in range(1, MAX_ONBOARDING_ATTEMPTS + 1):
                github_username = reply.content.strip()
                github_cog = self.bot.get_cog("GitHubCog")

                if github_cog is None:
                    print("[MessengerCog] GitHubCog not loaded; cannot handle onboarding username.")
                    return

                try:
                    is_valid, reason = await github_cog.handle_onboarding_username(member, github_username)
                except Exception as e:
                    print(f"[MessengerCog] Error passing onboarding username to GitHubCog for {member}: {e}")
                    is_valid, reason = False, "error"

                if is_valid:
                    # SUCCESS — username valid + contributor
                    await member.send(
                        f":white_check_mark: Nice! `{github_username}` is a contributor in a watched repo.\n"
                        "You're all set!"
                    )
                    return

                # Special case: GitHub account is already linked to another Discord user
                if reason == "already_linked":
                    await member.send(
                        ":no_entry: That GitHub account is **already linked** to another Discord user in this server.\n"
                        "If you think this is a mistake, please contact a server admin."
                    )
                    try:
                        await member.kick(
                            reason="Failed onboarding: GitHub account already linked to another Discord user."
                        )
                        print(f"[MessengerCog] Kicked {member} ({member.id}) - GitHub already linked.")
                    except Exception as e:
                        print(f"[MessengerCog] Failed to kick {member} ({member.id}) on already_linked: {e}")
                    return

                # For all other failures, fall through to the normal retry logic below
                if attempt < MAX_ONBOARDING_ATTEMPTS:
                    await member.send(
                        ":x: I couldn’t find that GitHub username as a contributor.\n"
                        "Please double-check and send your GitHub username again."
                    )

                    # Wait for the next reply
                    try:
                        reply = await self.bot.wait_for(
                            "message", check=check, timeout=ONBOARDING_TIMEOUT_SECONDS
                        )
                        continue
                    except asyncio.TimeoutError:
                        await member.send(
                            ":hourglass: You didn’t respond in time.\n"
                            "I have to remove you for now — feel free to rejoin anytime!"
                        )
                        await member.kick(reason="Failed onboarding: timeout during retries")
                        return

                # Last attempt failed
                await member.send(
                    ":no_entry: I still couldn’t verify your GitHub username after several tries.\n"
                    "Please rejoin once you've been added to the repo as a collaborator."
                )
                await member.kick(reason="Failed onboarding: invalid GitHub username (3 attempts)")
                return

        except discord.Forbidden:
            # They have DMs closed or blocked the bot – just ignore
            pass
        except Exception as e:
            # Optional: log any unexpected error
            print(f"[MessengerCog] Error DM'ing new member {member.id}: {e}")

    # -----------------------------
    # Admin command: !onboarding
    # -----------------------------

    @commands.command(
        name='onboarding',
        help=(
            'Enable or disable the onboarding DM + kick flow.\n'
            'Usage:\n'
            '  `!onboarding`            -> show current status\n'
            '  `!onboarding on`         -> enable onboarding\n'
            '  `!onboarding off`        -> disable onboarding'
        )
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def onboarding(self, ctx: commands.Context, mode: Optional[str] = None):
        """Toggles whether new members get DM onboarding + potential kick."""
        # No argument: show current status
        if mode is None:
            status = "enabled" if self.onboarding_enabled else "disabled"
            await ctx.send(f":wrench: Onboarding is currently **{status}**.")
            return

        mode = mode.lower()

        if mode in ("on", "enable", "enabled"):
            self.onboarding_enabled = True
            set_onboarding_enabled(True)
            save_data(self.bot.watched_repos, self.bot.notified_issues, self.bot.user_links)

            await ctx.send(
                ":white_check_mark: Onboarding has been **enabled**.\n"
                "New members will receive DMs and may be kicked if they do not respond."
            )
        elif mode in ("off", "disable", "disabled"):
            self.onboarding_enabled = False
            set_onboarding_enabled(False)
            save_data(self.bot.watched_repos, self.bot.notified_issues, self.bot.user_links)

            await ctx.send(
                ":no_entry_sign: Onboarding has been **disabled**.\n"
                "New members will *not* receive DMs or be kicked by this cog."
            )
        else:
            await ctx.send(
                ":x: Invalid mode.\n"
                "Use `!onboarding on` or `!onboarding off`."
            )

    @onboarding.error
    async def onboarding_error(self, ctx: commands.Context, error):
        """Error handler for the !onboarding command."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(":no_entry: You need **Administrator** permissions to use this command.")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send(":warning: This command can only be used in a server.")
        else:
            await ctx.send(f":x: An error occurred: {error}")
            # Re-raise so it still shows in logs
            raise error

async def setup(bot: commands.Bot):
    """Required setup function to load this cog."""
    await bot.add_cog(MessengerCog(bot))