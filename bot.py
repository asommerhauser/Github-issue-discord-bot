import discord
from discord.ext import commands
import aiohttp
import os
import asyncio
from config import DISCORD_BOT_TOKEN, get_github_headers
from utils.persistence import load_data


intents = discord.Intents.default()
intents.message_content = True  # Required to read messages for commands
intents.members = True

# Create the bot instance and remove the default help command
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# These will hold the bot's state, loaded on startup
bot.watched_repos = {}
bot.user_links = {}
bot.notified_issues = set()
bot.http_session = None


@bot.event
async def on_ready():
    """Called when the bot successfully logs in."""
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    
    bot.watched_repos, bot.notified_issues, bot.user_links = load_data()
    
    bot.http_session = aiohttp.ClientSession(headers=get_github_headers())
    
    try:
        await bot.load_extension("cogs.github")
        print("Loaded 'github' cog.")
        await bot.load_extension("cogs.help")
        print("Loaded 'help' cog.")
        await bot.load_extension("cogs.messenger")
        print("Loaded 'messenger' cog.")
    except Exception as e:
        print(f"Failed to load a cog: {e}")
        await bot.close()

@bot.event
async def on_close():
    """Called when the bot is shutting down."""
    if bot.http_session:
        await bot.http_session.close()
    print("Bot session closed.")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for all commands."""
    
    # Check if the error is a CommandNotFound
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f":question: Unknown command. Type `!help` to see all available commands.")
    # Check for permissions errors
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(f":no_entry_sign: You don't have permission to use that command.")
    # Handle other errors (and print them to console for debugging)
    else:
        print(f"An unhandled error occurred: {error}")
        await ctx.send(f":warning: An unexpected error occurred. Please try again later.")
        # Re-raise the error so we can see the full traceback in the console
        raise error


async def main():
    """Main function to start the bot."""
    async with bot:
        if not DISCORD_BOT_TOKEN:
            print("Error: Please set your DISCORD_BOT_TOKEN in config.py or as an environment variable.")
            return
            
        await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    
    print("Starting bot...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shut down by user.")

