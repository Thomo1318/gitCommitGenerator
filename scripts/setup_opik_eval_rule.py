import os
import sys

import requests


def main():
    api_key = os.getenv("OPIK_API_KEY")
    workspace = os.getenv("OPIK_WORKSPACE")
    url_base = os.getenv("OPIK_URL_OVERRIDE", "https://www.comet.com/opik")
    project_name = "gitCommitGenerator"

    if not api_key or not workspace:
        print("Error: OPIK_API_KEY and OPIK_WORKSPACE environment variables must be set.", file=sys.stderr)
        sys.exit(1)

    print(f"Setting up Opik Online Evaluation Rule for workspace: {workspace}")

    # 1. We need the project ID for gitCommitGenerator
    # The API is /api/v1/private/projects?name={name} (often we can just use the project name or we must query it)
    # Let's search for the project
    headers = {"Authorization": f"ApiKey {api_key}", "Comet-Workspace": workspace, "Content-Type": "application/json"}

    # Actually, Opik SDK handles this easily, but raw requests for rule creation needs projectId.
    # Let's fetch projects
    res = requests.get(f"{url_base}/api/v1/private/projects", headers=headers, params={"name": project_name})
    if res.status_code != 200:
        print(f"Failed to fetch projects: {res.status_code} {res.text}")
        sys.exit(1)

    data = res.json()
    projects = [p for p in data.get("content", []) if p["name"] == project_name]
    if not projects:
        print(
            f"Project '{project_name}' not found. Please run the gitCommitGenerator at least once so the project is created."
        )
        sys.exit(1)

    project_id = projects[0]["id"]
    print(f"Found project ID: {project_id}")

    # 2. Create the rule
    rule_payload = {
        "name": "Conventional Commit Quality",
        "type": "llm_as_judge",
        "action": "evaluator",
        "project_id": project_id,
        "sampling_rate": 1.0,
        "code": {
            "model": {"name": "gpt-4o", "temperature": 0.0},
            "messages": [
                {
                    "role": "user",
                    "content": "You are an expert software engineer evaluating an AI that generates Conventional Commit messages.\nYour task is to determine if the generated commit message accurately reflects the changes in the git diff and strictly follows the Conventional Commits specification.\n\nINPUT GIT DIFF:\n{{input.diff_output}}\n\nGENERATED COMMIT MESSAGE:\n{{output}}\n\nCRITERIA:\n1. Format: Does it follow the `<emoji> <type>(<scope>): <description>` format?\n2. Accuracy: Does the description accurately summarize the actual code changes in the diff?\n3. Length: Is the header concise (under 72 characters)?\n\nOutput a score of 1.0 if it meets all criteria, or 0.0 if it fails any of them. Provide a brief rationale.",
                }
            ],
            "variables": {"input.diff_output": "input.diff_output", "output": "output"},
        },
    }

    create_res = requests.post(f"{url_base}/api/v1/private/automations/evaluators", headers=headers, json=rule_payload)

    if create_res.status_code in [200, 201]:
        print("Successfully created Online Evaluation Rule: 'Conventional Commit Quality'")
    else:
        print(f"Failed to create rule: {create_res.status_code} {create_res.text}")
        # Note: it might fail if it already exists, that's fine.


if __name__ == "__main__":
    main()
