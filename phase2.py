import re
import requests
import yaml
from requests.auth import HTTPBasicAuth
from collections import defaultdict
import pickle
import os
import matplotlib.pyplot as plt
from dotenv import load_dotenv


CHECKPOINT_FILE = "checkpoint.pkl"

# Load configuration
with open("config.yaml") as f:
    config = yaml.safe_load(f)

load_dotenv()
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
PROJECT_KEY = os.getenv("JIRA_PROJECT")


auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
headers = {"Accept": "application/json"}


def extract_server_mentions(text):
    if not text:
        return []
    # Matches words like srv-app01, srv-db02 ignoring case
    return [m.lower() for m in re.findall(r'\b(srv-[\w-]+)\b', text, flags=re.IGNORECASE)]


def save_checkpoint(token, issues):
    with open(CHECKPOINT_FILE, "wb") as f:
        pickle.dump({"next_page_token": token, "issues": issues}, f)


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "rb") as f:
            checkpoint = pickle.load(f)
            print(f"Resuming from checkpoint: {len(checkpoint['issues'])} issues, token: {checkpoint['next_page_token']}")
            return checkpoint
    return {"next_page_token": None, "issues": []}


def fetch_all_issues_paginated():
    url = f"https://{JIRA_DOMAIN}/rest/api/3/search/jql"
    max_results = 8
    state = load_checkpoint()
    next_page_token = state["next_page_token"]
    all_issues = state["issues"]

    while True:
        query = {
            "jql": f"project={PROJECT_KEY}",
            "maxResults": max_results,
            "fields": "description"
        }
        if next_page_token:
            query["nextPageToken"] = next_page_token

        resp = requests.get(url, headers=headers, auth=auth, params=query)
        if resp.status_code != 200:
            print(f"Failed to fetch issues: {resp.status_code} {resp.text}")
            break

        data = resp.json()
        batch = data.get("issues", [])
        all_issues.extend(batch)
        next_page_token = data.get("nextPageToken")
        save_checkpoint(next_page_token, all_issues)

        if not next_page_token:
            break

    return all_issues


def main():
    issues = fetch_all_issues_paginated()
    os.remove(CHECKPOINT_FILE)
    server_count = defaultdict(int)
    unknown_count = 0

    for issue in issues:
        description_field = issue["fields"].get("description", {}) or {}
        text = ""

        # Extract plain text from Atlassian Document Format (ADF)
        try:
            content = description_field.get("content", [])
            for block in content:
                for chunk in block.get("content", []):
                    if chunk.get("type") == "text":
                        text += chunk.get("text", "") + " "
        except Exception as e:
            print(f"Error parsing description: {e}")

        mentioned = extract_server_mentions(text)
       

        valid_found = False

        for srv in mentioned:
            server_count[srv] += 1
            valid_found = True

        if not valid_found:
            unknown_count += 1

    # Add unknowns to the count dictionary for visualization
    server_count["UNKNOWN/INVALID"] = unknown_count

    # Visualize
    servers_sorted = sorted(server_count.keys())
    counts_sorted = [server_count[s] for s in servers_sorted]

    plt.figure(figsize=(12, 6))
    colors = ['#d62728' if s == "UNKNOWN/INVALID" else '#1f77b4' for s in servers_sorted]
    bars = plt.bar(servers_sorted, counts_sorted, color=colors)
    plt.title("Number of Tickets Mentioning Each Server")
    plt.xlabel("Server")
    plt.ylabel("Ticket Count")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Add counts on top of bars
    for bar, count in zip(bars, counts_sorted):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), str(count),
                 ha='center', va='bottom')

    plt.show()


    

if __name__ == "__main__":
    main()