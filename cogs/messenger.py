import asyncio
import discord
from discord.ext import commands


class MessengerCog(commands.Cog):
    """Cog responsible for messaging new members in DMs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """DM anyone who joins the server."""
        # Ignore bots joining
        if member.bot:
            return

        try:
            await member.send(
                "👋 Hey! Welcome to the server.\n\n"
                "I'm the bot that helps with GitHub + notifications. "
                "Before we get started — what's your **GitHub username**?\n"
                "Just reply to this DM with your username (no @ needed)."
            )

            def check(message: discord.Message) -> bool:
                return (
                    message.author.id == member.id and isinstance(message.channel, discord.DMChannel)
                )
            
            try:
                reply: discord.Message = await self.bot.wait_for("message", check=check, timeout=500)
            except asyncio.TimeoutError:
                # No reply from user - remove from server
                try:
                    await member.send(
                        "⏳ Hey! You didn’t respond with your GitHub username, "
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


async def setup(bot: commands.Bot):
    """Required setup function to load this cog."""
    await bot.add_cog(MessengerCog(bot))