import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

CHECK_INTERVAL_MINUTES = 15
ONBOARDING_TIMEOUT_SECONDS = 500


DATA_FILE_PATH = os.environ.get("DATA_FILE_PATH", "bot_data.json")

def get_github_headers():
    """Constructs the headers for GitHub API calls."""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
        print("Using GitHub Token for API calls.")
    else:
        print("Warning: No GitHub Token provided. You will be rate-limited (60 req/hr).")
    return headers


