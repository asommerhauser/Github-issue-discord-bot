import json
import os
from config import DATA_FILE_PATH

_onboarding_settings = {
    "enabled": False
}
    
def get_onboarding_enabled() -> bool:
    """Return whether onboarding is enabled (global flag)."""
    return _onboarding_settings.get("enabled", True)


def set_onboarding_enabled(value: bool) -> None:
    """Set whether onboarding is enabled and keep it in memory."""
    _onboarding_settings["enabled"] = bool(value)

def load_data():
    """Loads the watch list and notified issues from the JSON file."""
    watched_repos = {}
    notified_issues = set()
    user_links = {}
    
    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, 'r') as f:
                data = json.load(f)
                
                raw_watched_repos = data.get('watched_repos', {})
                migrated_watched_repos = {}
                migrated_user_links = {}
                data_was_migrated = False

                if raw_watched_repos:
                    try:
                        first_key = next(iter(raw_watched_repos))
                        first_val = raw_watched_repos[first_key]
                    except StopIteration:
                        first_val = None  

                    if isinstance(first_val, int):  
                        print("Old data format detected (v1). Migrating...")
                        for repo, channel_id in raw_watched_repos.items():
                            migrated_watched_repos[repo] = {
                                "channel_id": channel_id,
                                "labels": ["good first issue"],  
                                "watch_type": "issues" 
                            }
                        watched_repos = migrated_watched_repos
                        data_was_migrated = True
                        print("Migration v1 complete.")
                        
                    else:  
                        watched_repos = raw_watched_repos
                        for repo, repo_data in watched_repos.items():
                            if "watch_type" not in repo_data:
                                repo_data["watch_type"] = "issues" 
                                data_was_migrated = True
                        if data_was_migrated:
                             print("Migrated v2 data to include 'watch_type: issues' default.")
                
                notified_issues = set(data.get('notified_issues', []))
                
                onboarding_data = data.get('onboarding')
                if isinstance(onboarding_data, dict) and "enabled" in onboarding_data:
                    _onboarding_settings["enabled"] = bool(onboarding_data["enabled"])

                raw_user_links = data.get('user_links', {})
                if isinstance(raw_user_links, dict):
                    user_links = {int(k): v for k, v in raw_user_links.items()}
                else:
                    user_links = {}

            print(f"Loaded data from {DATA_FILE_PATH}")
            
            if data_was_migrated:
                save_data(watched_repos, notified_issues, user_links)

        except Exception as e:
            print(f"Error reading or migrating {DATA_FILE_PATH}: {e}. Starting with empty data.")
            watched_repos = {}
            notified_issues = set()
            user_links = {}
    else:
        print(f"{DATA_FILE_PATH} not found. Starting with empty data.")
        
    return watched_repos, notified_issues, user_links

def save_data(watched_repos, notified_issues, user_links):
    """Saves the current state to the JSON file."""
    try:
        with open(DATA_FILE_PATH, 'w') as f:
            data = {
                'watched_repos': watched_repos,
                'notified_issues': list(notified_issues),
                'onboarding': _onboarding_settings,
                'user_links': user_links
            }
            json.dump(data, f, indent=4)
        print(f"Saved data to {DATA_FILE_PATH}")
    except IOError as e:
        print(f"Error saving data: {e}")

