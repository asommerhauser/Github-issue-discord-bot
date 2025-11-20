import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta
from utils.persistence import save_data
from config import CHECK_INTERVAL_MINUTES, get_github_headers

class GitHubCog(commands.Cog):
    """Cog for handling all GitHub-related commands and tasks."""
    
    def __init__(self, bot):
        self.bot = bot
        self.check_issues_loop.start()

    def cog_unload(self):
        """Called when the cog is unloaded."""
        self.check_issues_loop.cancel()


    @commands.command(name='watch', 
                      help='Watch a repo for issues, pull requests, or both.\n'
                           'Usage: `!watch owner/repo [labels...] [--type <type>]`\n'
                           'Types: `issues` (default), `prs`, `all`\n'
                           'Example: `!watch owner/repo "help wanted" --type all`\n'
                           'Example: `!watch owner/repo --type prs`')
    async def watch_repo(self, ctx, repo_name: str, *args: str):
        """Adds a repository to the watch list for the current channel."""
        repo_name = repo_name.strip()
        
        if '/' not in repo_name or len(repo_name.split('/')) != 2:
            await ctx.send(f":x: Invalid format. Please use `owner/repo` (e.g., `!watch microsoft/vscode`)")
            return

        labels = []
        watch_type = "issues" 
        possible_types = ["issues", "prs", "all"]
        
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.lower() == "--type":
                if i + 1 < len(args) and args[i+1].lower() in possible_types:
                    watch_type = args[i+1].lower()
                    i += 2 # Skip both --type and its value
                    continue
                else:
                    await ctx.send(f":x: Invalid value for `--type`. Must be `issues`, `prs`, or `all`.")
                    return
            else:
                labels.append(arg)
                i += 1
        

        loading_msg = await ctx.send(f":mag: Verifying repository `{repo_name}`...")

        try:
            repo_url = f"https://api.github.com/repos/{repo_name}"
            async with self.bot.http_session.get(repo_url) as response:
                if response.status == 404:
                    await loading_msg.edit(content=f":x: Error: Repository `{repo_name}` not found. Please check the spelling.")
                    return
                elif response.status != 200:
                    await loading_msg.edit(content=f":warning: Could not verify repository. GitHub API returned status `{response.status}`.")
                    return

            valid_labels = [] 
            
            if labels: 
                await loading_msg.edit(content=f":mag: Verifying labels for `{repo_name}`...")
                
                repo_labels_url = f"https://api.github.com/repos/{repo_name}/labels"
                repo_label_names = set()
                page = 1

                
                while True:
                    params = {"page": page, "per_page": 100}
                    async with self.bot.http_session.get(repo_labels_url, params=params) as response:
                        if response.status != 200:
                            await loading_msg.edit(content=f":warning: Could not fetch labels for `{repo_name}`. GitHub API returned status `{response.status}`.")
                            return
                        
                        label_data = await response.json()
                        if not label_data:
                            # No more labels, break the loop
                            break
                        
                        for label in label_data:
                            repo_label_names.add(label['name'].lower()) # Store lowercase for comparison
                        
                        # If we received fewer than 100 labels, this is the last page
                        if len(label_data) < 100:
                            break
                        page += 1

                
                invalid_labels = []
                for user_label in labels:
                    if user_label.lower() not in repo_label_names:
                        invalid_labels.append(f"`{user_label}`")
                    else:
                        valid_labels.append(user_label) 

                if invalid_labels:
                    invalid_str = ", ".join(invalid_labels)
                    await loading_msg.edit(content=f":x: Error: Repository `{repo_name}` found, but the following labels do not exist: {invalid_str}")
                    return
                
                if not valid_labels:
                    if labels:
                        await loading_msg.edit(content=f":x: Error: No valid labels were provided, but you specified some.")
                        return
            
            #All checks passed, save the data
            channel_id = ctx.channel.id
            start_time_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            self.bot.watched_repos[repo_name] = {
                "channel_id": channel_id,
                "labels": valid_labels, 
                "watch_since_time": start_time_iso,
                "watch_type": watch_type
            }
            
            save_data(self.bot.watched_repos, self.bot.notified_issues, self.bot.user_links)
            
            
            type_str = {
                "issues": "issues",
                "prs": "pull requests",
                "all": "issues and pull requests"
            }[watch_type]

            if valid_labels:
                label_str = ", ".join([f"`{l}`" for l in valid_labels])
                await loading_msg.edit(content=f":white_check_mark: Now watching `{repo_name}` for new **{type_str}** with labels: {label_str}. \nNotifications will be sent to this channel.")
            else:
                await loading_msg.edit(content=f":white_check_mark: Now watching `{repo_name}` for **all new {type_str}**. \nNotifications will be sent to this channel.")

        except aiohttp.ClientError as e:
            print(f"Network error during repo verification: {e}")
            await loading_msg.edit(content=f":warning: A network error occurred while trying to verify the repository.")
        except Exception as e:
            print(f"Unexpected error in !watch: {e}")
            await loading_msg.edit(content=f":warning: An unexpected error occurred.")
            raise e 

    @watch_repo.error
    async def watch_repo_error(self, ctx, error):
        """Error handler for the !watch command."""
        if isinstance(error, commands.MissingRequiredArgument):
            if error.param.name == 'repo_name':
                await ctx.send(f":warning: You forgot the repository name! \nUsage: `!watch owner/repo \"label one\"`")
        else:
            await ctx.send(f":x: An error occurred: {error}")
            raise error 

    @commands.command(name='unwatch', 
                      help='Stop watching a repository.\nUsage: `!unwatch owner/repo`')
    async def unwatch_repo(self, ctx, repo_name: str):
        """Removes a repository from the watch list."""
        repo_name = repo_name.strip()
        
        if repo_name in self.bot.watched_repos:
            del self.bot.watched_repos[repo_name]
            save_data(self.bot.watched_repos, self.bot.notified_issues, self.bot.user_links)
            await ctx.send(f":x: Stopped watching `{repo_name}`.")
        else:
            await ctx.send(f":grey_question: I am not currently watching `{repo_name}`.")

    @unwatch_repo.error
    async def unwatch_repo_error(self, ctx, error):
        """Error handler for the !unwatch command."""
        if isinstance(error, commands.MissingRequiredArgument):
            if error.param.name == 'repo_name':
                await ctx.send(f":warning: You forgot the repository name! \nUsage: `!unwatch owner/repo`")
        else:
            await ctx.send(f":x: An error occurred: {error}")
            raise error 
        
    @commands.command(name='list', 
                      help='Show all repositories being watched in this server.')
    async def list_watched(self, ctx):
        """Lists all repositories and their notification channels."""
        if not self.bot.watched_repos:
            await ctx.send("I am not watching any repositories.")
            return
        
        embed = discord.Embed(title="Watched Repositories", color=discord.Color.blue())
        
        description = ""
        count = 0
        # Only show repos being watched in this guild (server)
        for repo, data in self.bot.watched_repos.items():
            channel = self.bot.get_channel(data['channel_id'])
            # Check if channel is in the same server this command was run
            if channel and channel.guild == ctx.guild:
                count += 1
                channel_id = data['channel_id']
                labels = data['labels']
                watch_type = data.get("watch_type", "issues") # Default to issues
                channel_name = f"<#{channel_id}>"
                
                if labels:
                    label_str = ", ".join([f"`{l}`" for l in labels])
                else:
                    label_str = "**All**"
                
                # Try to get a formatted time string
                time_str = " (Time not set)"
                if data.get('watch_since_time'):
                    try:
                        time_dt = datetime.fromisoformat(data['watch_since_time'].replace('Z', '+00:00'))
                        # Format as relative time for Discord <t:TIMESTAMP:R>
                        time_str = f" (since <t:{int(time_dt.timestamp())}:R>)"
                    except:
                        pass    
                
                type_str = {
                    "issues": "Issues Only",
                    "prs": "PRs Only",
                    "all": "Issues & PRs"
                }[watch_type]

                description += (f"**`{repo}`**{time_str}\n"
                              f"• Channel: {channel_name}\n"
                              f"• Type: **{type_str}**\n"
                              f"• Labels: {label_str}\n\n")
        
        if count == 0:
            await ctx.send("I am not watching any repositories in this server.")
            return

        embed.description = description
        await ctx.send(embed=embed)

    @commands.command(name='links',
                    help='Show all Discord → GitHub account links.')
    async def list_links(self, ctx):
        """Lists all Discord users linked to GitHub usernames."""
        user_links = getattr(self.bot, "user_links", {})

        if not user_links:
            await ctx.send("There are no linked accounts.")
            return

        lines = []
        for discord_id, github_username in user_links.items():
            member = ctx.guild.get_member(discord_id)
            if member:
                lines.append(f"- {member.mention} → `{github_username}`")
            else:
                lines.append(f"- <@{discord_id}> → `{github_username}`")

        await ctx.send("**Linked Accounts:**\n" + "\n".join(lines))

    @list_links.error
    async def list_links_error(self, ctx, error):
        """Error handler for the !links command."""
        await ctx.send(f":x: An error occurred: {error}")
        raise error
    
    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_issues_loop(self):
        """The main background loop that checks GitHub for new issues."""
        
        current_run_time_utc = datetime.now(timezone.utc)
        print(f"[{datetime.now()}] Running GitHub check...")
        
        if not self.bot.watched_repos:
            print("No repos to watch. Skipping check.")
            return

        base_params = {"state": "open", "sort": "updated", "direction": "desc"}
        
        current_notified_issues = set(self.bot.notified_issues)
        repos_to_remove = []
        data_was_modified = False

        for repo, data in list(self.bot.watched_repos.items()):
            channel_id = data['channel_id']
            labels = data['labels']
            watch_type = data.get("watch_type", "issues") 
            
            params = base_params.copy()
            
            if labels:
                params["labels"] = ",".join(labels)
            
            repo_since_time = data.get('watch_since_time')
            
            if repo_since_time:
                try:
                    since_dt = datetime.fromisoformat(repo_since_time.replace('Z', '+00:00'))
                    since_dt_buffered = since_dt - timedelta(seconds=1)
                    params["since"] = since_dt_buffered.isoformat().replace('+00:00', 'Z')
                except ValueError:
                    print(f"  - Error: Invalid time format for {repo}: {repo_since_time}. Fetching all.")
                    # Fallback: Don't use 'since' this time if format is bad
            else:
                # This is an old entry from before we tracked time.
                print(f"  - No 'watch_since_time' for {repo}. Fetching all and setting time for next run.")
                data_was_modified = True # Mark to save the new time
            
            url = f"https://api.github.com/repos/{repo}/issues"
            
            
            type_log_str = {
                "issues": "issues only",
                "prs": "PRs only",
                "all": "issues and PRs"
            }[watch_type]
            if labels:
                print(f"  - Checking {repo} for {type_log_str} with labels: {params['labels']}")
            else:
                print(f"  - Checking {repo} for all new {type_log_str}")
            
                
            if 'since' in params:
                print(f"  - Checking for items updated since: {params['since']}")
            
            try:
                async with self.bot.http_session.get(url, params=params) as response:
                    
                    if response.status == 200:
                        items = await response.json() 
                        if not items:
                            print(f"  - No matching items found for {repo}.")
                            continue
                        
                        print(f"  - Found {len(items)} matching items for {repo}.")
                        
                        for item in items: 
                            
                            is_pr = 'pull_request' in item

                            if watch_type == "issues" and is_pr:
                                print(f"    - Ignoring Pull Request (watching issues only): {repo}#{item['number']}")
                                continue
                            elif watch_type == "prs" and not is_pr:
                                print(f"    - Ignoring Issue (watching PRs only): {repo}#{item['number']}")
                                continue

                            issue_id = f"{repo}#{item['number']}"
                            issue_created_at = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
                            
                            watch_started_at = None
                            if repo_since_time:
                                try:
                                    watch_started_at = datetime.fromisoformat(repo_since_time.replace('Z', '+00:00'))
                                except ValueError:
                                    pass 
                            
                            passes_newness_check = issue_id not in self.bot.notified_issues
                            
                            passes_time_check = True 
                            if watch_started_at:
                                passes_time_check = (issue_created_at >= watch_started_at)
                            else:
                                print(f"    - No watch_started_at for {issue_id}, relying on notified_issues set.")

                            if passes_newness_check and passes_time_check:
                                print(f"    - NEW Item Found: {issue_id} (Type: {'PR' if is_pr else 'Issue'})")
                                current_notified_issues.add(issue_id)
                                
                                channel = self.bot.get_channel(channel_id)
                                if channel:
                                    await self.send_notification(channel, repo, item, labels, is_pr)
                                else:
                                    print(f"    - Error: Channel {channel_id} not found for repo {repo}.")
                            elif issue_id in self.bot.notified_issues:
                                print(f"    - Ignoring already notified item: {issue_id}")
                            else:
                                if watch_started_at:
                                    print(f"    - Ignoring old item: {issue_id} (created {issue_created_at}, watching since {watch_started_at})")
                                else:
                                    print(f"    - Ignoring old item: {issue_id} (created {issue_created_at}, no watch time set)")

                    
                    elif response.status == 404:
                        print(f"  - Error: Repository {repo} not found (404).")
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            await channel.send(f":warning: Repository `{repo}` could not be found. It may have been deleted or renamed. Removing from watch list.")
                        repos_to_remove.append(repo)

                    else:
                        print(f"  - Error: GitHub API returned {response.status} for {repo}.")
                        
            except aiohttp.ClientError as e:
                print(f"  - Error: Network or client error checking {repo}: {e}")
            
            # Update this repo's check time to the time this loop *started*.
            if self.bot.watched_repos.get(repo): # Check if it wasn't deleted
                self.bot.watched_repos[repo]['watch_since_time'] = current_run_time_utc.isoformat().replace('+00:00', 'Z')
                data_was_modified = True
            
            await asyncio.sleep(2) 

        for repo in repos_to_remove:
            if repo in self.bot.watched_repos:
                del self.bot.watched_repos[repo]
                data_was_modified = True 
                
        self.bot.notified_issues.update(current_notified_issues)
        
        # Only save if we actually need to
        if data_was_modified:
            save_data(self.bot.watched_repos, self.bot.notified_issues, self.bot.user_links)
        
        print("GitHub check finished.")

    async def send_notification(self, channel, repo, issue, watched_labels, is_pr):
        """Formats and sends a single issue notification to a channel."""
        
        # Simplify the title per your request
        item_type_str = "New Pull Request" if is_pr else "New Issue"
        color = discord.Color.blue() if is_pr else discord.Color.green()
        
        embed = discord.Embed(
            title=item_type_str,
            description=issue['title'],
            url=issue['html_url'],
            color=color,
            timestamp=datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
        )
        
        # Add repo name as a field so it's clear
        embed.add_field(name="Repository", value=f"`{repo}`", inline=False)
        
        item_type_field_name = "PR Number" if is_pr else "Issue Number"
        embed.add_field(name=item_type_field_name, value=f"#{issue['number']}", inline=True)
        
        embed.add_field(name="Created By", value=f"[{issue['user']['login']}]({issue['user']['html_url']})", inline=True)
        
        issue_labels = [label['name'] for label in issue['labels']]
        
        # Only highlight labels if we are watching for specific ones
        if watched_labels:
            watched_label_set_lower = set(l.lower() for l in watched_labels)
            
            formatted_labels = []
            for name in issue_labels:
                if name.lower() in watched_label_set_lower:
                    formatted_labels.append(f"**`{name}`** :star:") # Highlights the label that matched
                else:
                    formatted_labels.append(f"`{name}`")
            
            if formatted_labels:
                embed.add_field(name="Labels", value=', '.join(formatted_labels), inline=False)
        
        elif issue_labels:
            # If we're watching ALL issues, just list the labels without highlighting
            formatted_labels = [f"`{name}`" for name in issue_labels]
            embed.add_field(name="Labels", value=', '.join(formatted_labels), inline=False)
            
        
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Error: Bot does not have permission to send messages in channel {channel.id} ({channel.name}).")
        except Exception as e:
            print(f"Error sending message: {e}")

    @check_issues_loop.before_loop
    async def before_check_loop(self):
        """Waits for the bot to be logged in before starting the loop."""
        await self.bot.wait_until_ready()

    async def is_collaborator_for_repo(self, github_username: str) -> bool:
        """
        Checks the list of repos to determine if the GitHub username exists as a collaborator
        in ANY of the watched repos.
        """

        if not getattr(self.bot, "watched_repos", None):
            print("[GitHubCog] No watched repos configured; cannot validate collaborators.")
            return False
        
        github_username = github_username.lower()

        session = getattr(self.bot, "http_session", None)
        headers = get_github_headers()

        async def check_repo(full_name: str) -> bool:
            owner, repo = full_name.split("/", 1)
            url = f"https://api.github.com/repos/{owner}/{repo}/collaborators/{github_username}"

            async with session.get(url, headers=headers) as resp:
                if resp.status == 204:
                    print(f"[GitHubCog] {github_username} IS a collaborator on {full_name}")
                    return True
                elif resp.status == 404:
                    return False
                else:
                    print(f"[GitHubCog] Failed to fetch collaborator status for {full_name} (status {resp.status})")
                    return False

        # Check each watched repo in turn
        for full_name in self.bot.watched_repos.keys():
            try:
                if await check_repo(full_name):
                    return True
            except Exception as e:
                print(f"[GitHubCog] Error while checking collaborators for {full_name}: {e}")

        print(f"[GitHubCog] {github_username} is not a collaborator on any watched repo.")
        return False


    async def handle_onboarding_username(self, member: discord.Member, github_username: str) -> bool:
            """
            Handle a GitHub username collected during onboarding.

            Returns:
                True  -> user is a collaborator on at least one watched repo (and is linked)
                False -> user is NOT a collaborator / invalid username
            """
            github_username = github_username.strip()

            print(
                f"[Onboarding DEBUG] Discord user {member} ({member.id}) "
                f"submitted GitHub username: '{github_username}'"
            )

            if not github_username:
                return False

            # Validate that this username is a collaborator on at least one watched repo
            is_collab = await self.is_collaborator_for_repo(github_username)
            if not is_collab:
                print(
                    f"[GitHubCog] Onboarding failed: Discord user {member} ({member.id}) "
                    f"GitHub '{github_username}' not found as collaborator in any watched repo."
                )
                return False

            # Store the link on the bot so other cogs can use it
            self.bot.user_links[member.id] = github_username
            save_data(self.bot.watched_repos, self.bot.notified_issues, self.bot.user_links)

            print(f"[GitHubCog] Linked Discord user {member} ({member.id}) to GitHub '{github_username}'")

            return True

async def setup(bot):
    """Required setup function to load the cog."""
    await bot.add_cog(GitHubCog(bot))

