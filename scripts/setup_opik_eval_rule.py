import os
import sys

import requests


def create_geval_rule(project_id: str, name: str, prompt: str, headers: dict, url_base: str):
    rule_payload = {
        "name": name,
        "type": "llm_as_judge",
        "action": "evaluator",
        "project_id": project_id,
        "sampling_rate": 1.0,
        "code": {
            "model": {"name": "gpt-4o", "temperature": 0.0},
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "variables": {"input.diff_output": "input.diff_output", "output": "output"},
        },
    }

    res = requests.post(f"{url_base}/api/v1/private/automations/evaluators", headers=headers, json=rule_payload)
    if res.status_code in [200, 201]:
        print(f"Successfully created GEval Rule: '{name}'")
    else:
        print(f"Failed to create rule '{name}': {res.status_code} {res.text}")


def main():
    api_key = os.getenv("OPIK_API_KEY")
    workspace = os.getenv("OPIK_WORKSPACE")
    url_base = os.getenv("OPIK_URL_OVERRIDE", "https://www.comet.com/opik")
    project_name = "gitCommitGenerator"

    if not api_key or not workspace:
        print("Error: OPIK_API_KEY and OPIK_WORKSPACE environment variables must be set.", file=sys.stderr)
        sys.exit(1)

    print(f"Setting up Opik GEval Rules for workspace: {workspace}")

    headers = {"Authorization": f"ApiKey {api_key}", "Comet-Workspace": workspace, "Content-Type": "application/json"}
    res = requests.get(f"{url_base}/api/v1/private/projects", headers=headers, params={"name": project_name})
    if res.status_code != 200:
        print(f"Failed to fetch projects: {res.status_code} {res.text}")
        sys.exit(1)

    data = res.json()
    projects = [p for p in data.get("content", []) if p["name"] == project_name]
    if not projects:
        print(f"Project '{project_name}' not found. Please run git-cg at least once so the project is created.")
        sys.exit(1)

    project_id = projects[0]["id"]
    print(f"Found project ID: {project_id}")

    # 1. Diff-Commit Semantic Alignment
    create_geval_rule(
        project_id,
        "Diff-Commit Semantic Alignment",
        "You are an expert code reviewer evaluating a git commit message against its diff.\n"
        "Does the commit message accurately capture the code changes in the diff without hallucinations or missing key semantics?\n\n"
        "INPUT GIT DIFF:\n{{input.diff_output}}\n\n"
        "GENERATED COMMIT MESSAGE:\n{{output}}\n\n"
        "Output a score from 0.0 (completely inaccurate/hallucinated) to 1.0 (perfect alignment). Provide a brief rationale.",
        headers,
        url_base,
    )

    # 2. Intent Selection Accuracy
    create_geval_rule(
        project_id,
        "Intent Selection Accuracy",
        "You are a strict Conventional Commits evaluator.\n"
        "Was the correct cc_type (e.g., feat, fix, refactor, chore) chosen given the semantic nature of the diff?\n\n"
        "INPUT GIT DIFF:\n{{input.diff_output}}\n\n"
        "GENERATED COMMIT MESSAGE:\n{{output}}\n\n"
        "Output a score of 1.0 if the correct type was chosen, 0.5 if plausible but sub-optimal, or 0.0 if completely incorrect. Provide a brief rationale.",
        headers,
        url_base,
    )

    # 3. Conciseness Quality
    create_geval_rule(
        project_id,
        "Conciseness Quality",
        "You are a technical editor evaluating the conciseness of a commit message.\n"
        "Is the description maximally concise without losing critical meaning? Does it avoid redundant phrasing like 'This commit updates' or 'Added code to'?\n\n"
        "GENERATED COMMIT MESSAGE:\n{{output}}\n\n"
        "Output a score from 0.0 (extremely verbose) to 1.0 (optimally concise). Provide a brief rationale.",
        headers,
        url_base,
    )


if __name__ == "__main__":
    main()
