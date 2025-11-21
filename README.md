# Discord GitHub Issue Tracker Bot

A Discord bot that monitors GitHub repositories and sends notifications about new issues and pull requests with specific labels to designated channels.

[Invitation Link](https://discord.com/oauth2/authorize?client_id=1431393106523197530&permissions=19456&integration_type=0&scope=bot)

## Features

- Watch GitHub repositories for new issues, pull requests, or both
- Filter notifications by issue/PR labels
- Multiple channel support across different servers
- Persistent storage of watched repositories
- Command-based interface with detailed help
- Automatic repository and label validation
- Configurable check intervals
- Rich embed notifications with highlighting

## Requirements

- Python 3.8+
- discord.py==2.6.4
- aiohttp==3.13.1
- python-dotenv==1.1.1

## Setup

1. Clone this repository
2. Create a virtual environment:
```powershell
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies:
```powershell
pip install -r requirements.txt
```

4. Create a `.env` file with your tokens:
```env
DISCORD_BOT_TOKEN=your_discord_token
GITHUB_TOKEN=your_github_token
```

5. Run the bot:
```powershell
python bot.py
```

## Commands

- `!watch owner/repo [labels...] [--type <type>]` - Watch a repository for issues, PRs, or both
  - Types: `issues` (default), `prs`, `all`
  - Examples: 
    - `!watch microsoft/vscode "help wanted" "bug"`
    - `!watch owner/repo --type prs`
    - `!watch owner/repo "enhancement" --type all`
- `!unwatch owner/repo` - Stop watching a repository
- `!list` - Show all watched repositories in the current server
- `!help [command]` - Display help information for all commands or a specific command

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
GITHUB_TOKEN=your_github_token  # Optional but recommended
DATA_FILE_PATH=bot_data.json    # Optional, defaults to bot_data.json
```

### Configuration Options

Edit `config.py` to modify:
- `CHECK_INTERVAL_MINUTES` - How often to check for new issues/PRs (default: 15 minutes)
- `DATA_FILE_PATH` - Location of the persistent data file
- GitHub API headers and version settings

### GitHub Token

While optional, providing a GitHub token is highly recommended:
- **Without token**: Rate limited to 60 requests per hour
- **With token**: Rate limited to 5000 requests per hour
- Get a token at: https://github.com/settings/tokens

## Github Linking & Onboarding (Optional)

This bot includes an optional **GitHub-verification onboarding system**. When enabled, every new member must verify their GitHub username through DM before staying in the server.

### How It Works
- When a new user joins, the bot DMs them asking for their **GitHub username**.
- The username must belong to a **collaborator on any currently watched repository**.
- If valid:
  - The user is linked to that GitHub account
  - (Optional) They are assigned the configured *GitHub Collaborator* role
- If invalid, already linked elsewhere, or they don’t respond:
  - The bot **kicks** them from the server after the configured timeout/attempts.

### Enabling / Disabling Onboarding
Admins can toggle onboarding at any time:

- !onboarding on
- !onboarding off
- !onboarding

### Commands for manual linking

- !link [github_username]
- !link @user [github_username]
- !links

### Required Config Values

ONBOARDING_TIMEOUT_SECONDS = 60
MAX_ONBOARDING_ATTEMPTS = 3
GITHUB_COLLAB_ROLE_ID = 123456789012345678

## Project Structure

```
├── bot.py              # Main bot file
├── config.py           # Configuration settings
├── requirements.txt    # Python dependencies
├── bot_data.json       # Persistent data storage
├── cogs/               # Bot command modules
│   ├── github.py       # GitHub monitoring commands
│   └── help.py         # Help command
└── utils/              # Utility modules
    └── persistence.py  # Data persistence functions
```

## Usage Examples

### Basic Repository Watching
```
!watch microsoft/vscode
!watch facebook/react "help wanted" "good first issue"
```

### Pull Request Monitoring
```
!watch owner/repo --type prs
!watch microsoft/vscode "enhancement" --type all
```

### Managing Watches
```
!list                    # See all watched repositories
!unwatch microsoft/vscode # Stop watching a repository
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License

## Support

Create an issue in the repository for support requests.
