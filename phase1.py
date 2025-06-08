import random
import requests
import yaml
from faker import Faker
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)


load_dotenv()
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
PROJECT_KEY = os.getenv("JIRA_PROJECT")

SERVERS = config["servers"]
PRIORITY_DIST = config.get("priority_distribution", {})

fake = Faker()

def generate_due_date():
    # Generate a random date between today and 30 days from now
    due_date = fake.date_between(start_date="today", end_date="+30d")
    return due_date.strftime("%Y-%m-%d")

def generate_description(servers):
    # Some example problem templates
    problem_templates = [
        "The system crashed when accessing {}.",
        "We're noticing performance degradation on {}.",
        "Connection timeout occurred with {}.",
        "Disk space alert triggered on {}.",
        "Frequent 500 errors seen on {}.",
        "Backup failed on {} last night.",
        "Unexpected shutdown of {} detected.",
        "Users can't reach {}.",
        "High CPU usage reported on {}.",
        "Memory leak suspected on {}."
    ]

    # Decide how many servers to mention
    rand = random.random()
    mentioned_servers = []

    if rand < 0.8:  # 80% chance to use valid server names
        count = random.choice([1, 2])
        mentioned_servers = random.sample(servers, count)
        mentioned_servers = [
            s.upper() if random.random() < 0.5 else s.lower()
            for s in mentioned_servers
        ]
    elif rand < 0.95:  # 15% chance to use invalid/malformed names
        mentioned_servers = [
            random.choice(["srv-news","srv-2025", "srv-1000"])
        ]
    else:  # 5% chance to omit server name completely
        mentioned_servers = ["server"]
        # If no servers were mentioned, use a generic placeholder


    server_list = ", ".join(mentioned_servers)
    problem_template = random.choice(problem_templates)
    problem_sentence = problem_template.format(server_list)


    return problem_sentence

def pick_by_distribution(distribution_dict):
    choices = list(distribution_dict.keys())
    weights = list(distribution_dict.values())
    return random.choices(choices, weights=weights, k=1)[0]

def create_issue_bulk(issues):
    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/bulk"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = {
        "issueUpdates": issues
    }

    resp = requests.post(
        url,
        auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN),
        json=payload,
        headers=headers
    )

    if resp.status_code != 201:
        print(f"Bulk issue creation failed: {resp.status_code} {resp.text}")
    else:
        print(f"Bulk created {len(issues)} issues successfully.")

def main():
    batch = []
    for i in range(5000):
        summary = f"Ticket {i}"
        priority = pick_by_distribution(PRIORITY_DIST)
        description = generate_description(SERVERS)
        duedate = generate_due_date()

        issue = {
            "fields": {
                "project": {"key": PROJECT_KEY},
                "assignee": {"id": "-1"},
                "summary": summary,
                "description": {
                    "content": [
                        {
                            "content": [
                                {
                                    "text": description,
                                    "type": "text"
                                }
                            ],
                            "type": "paragraph"
                        }
                    ],
                    "type": "doc",
                    "version": 1
                },
                "issuetype": {"name": "Task"},
                "priority": {"name": priority},
                "duedate": duedate
            }
        }

        batch.append(issue)

        if len(batch) == 50:
            create_issue_bulk(batch)
            batch.clear()

    # Handle any remaining issues
    if batch:
        create_issue_bulk(batch)

if __name__ == "__main__":
    main()