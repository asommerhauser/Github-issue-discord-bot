import asyncio
import discord
from discord.ext import commands
from config import ONBOARDING_TIMEOUT_SECONDS


class MessengerCog(commands.Cog):
    """Cog responsible for messaging new members in DMs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.onboarding_enabled = False

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
            
            github_username = reply.content.strip()

            await member.send(
                f"Thanks! I got your username as `{github_username}`. "
                "I'll use this in the future when we connect your GitHub activity."
            )


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
    async def onboarding(self, ctx: commands.Context, mode: str | None = None):
        """Toggles whether new members get DM onboarding + potential kick."""
        # No argument: show current status
        if mode is None:
            status = "enabled" if self.onboarding_enabled else "disabled"
            await ctx.send(f":wrench: Onboarding is currently **{status}**.")
            return

        mode = mode.lower()

        if mode in ("on", "enable", "enabled"):
            self.onboarding_enabled = True
            await ctx.send(
                ":white_check_mark: Onboarding has been **enabled**.\n"
                "New members will receive DMs and may be kicked if they do not respond."
            )
        elif mode in ("off", "disable", "disabled"):
            self.onboarding_enabled = False
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