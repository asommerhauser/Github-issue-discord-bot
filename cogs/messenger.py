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
                "We’ll be adding more features soon, but for now I'm just saying hi 😌"
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