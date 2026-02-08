import json

import requests


def load_credentials():
    try:
        with open(".colosseum_credentials.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


creds = load_credentials()
API_KEY = creds.get("api_key")
BASE_URL = "https://agents.colosseum.com/api"


def check_heartbeat():
    print("--- Fetching Heartbeat ---")
    response = requests.get("https://colosseum.com/heartbeat.md")
    if response.status_code == 200:
        skill_path = ".agent/skills/heartbeat/SKILL.md"
        with open(skill_path, "w") as f:
            f.write(response.text)
        print(f"Updated {skill_path}")
    else:
        print(f"Failed to fetch heartbeat: {response.status_code}")


def check_status():
    print("--- Checking Agent Status ---")
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(f"{BASE_URL}/agents/status", headers=headers)
    if response.status_code == 200:
        status = response.json()
        print(json.dumps(status, indent=2))
        return status
    print(f"Failed to fetch status: {response.status_code}")
    return None


if __name__ == "__main__":
    if not API_KEY:
        print("COLOSSEUM_API_KEY not found in .env")
    else:
        check_heartbeat()
        check_status()
