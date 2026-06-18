#!/usr/bin/env python
import argparse
import json

import opik


def compile_dataset(project_name: str, dataset_name: str, threshold: float):
    client = opik.Opik()

    print(f"Fetching traces for project '{project_name}' with score > {threshold}...")
    try:
        traces = client.search_traces(
            project_name=project_name, filter_string=f"feedback_scores.user_acceptance > {threshold}"
        )
    except Exception as e:
        print(f"Failed to fetch traces: {e}")
        return

    dataset = client.get_or_create_dataset(name=dataset_name)

    dataset_items = []
    rejected_commits = 0
    valid_commits = 0

    for trace in traces:
        # Opik TracePublic object has input, output, metadata.
        input_data = trace.input if isinstance(trace.input, dict) else {}
        metadata = trace.metadata if isinstance(trace.metadata, dict) else {}

        kwargs = input_data.get("kwargs", {})
        if isinstance(kwargs, str):
            try:
                kwargs = json.loads(kwargs)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse kwargs JSON for trace {trace.id}: {e}")
        if not isinstance(kwargs, dict):
            kwargs = {}

        telemetry = input_data.get("telemetry_state", {})
        if isinstance(telemetry, str):
            try:
                telemetry = json.loads(telemetry)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse telemetry_state JSON for trace {trace.id}: {e}")
        if not isinstance(telemetry, dict):
            telemetry = {}

        diff = metadata.get("diff_output")
        if not diff:
            diff = kwargs.get("diff_output")
        if not diff:
            diff = telemetry.get("diff_output")

        commit_plan = metadata.get("commit_plan")
        if not commit_plan:
            commit_plan = kwargs.get("commit_plan")
        if not commit_plan:
            # telemetry_state has commit_plan_json, we can use that or wait
            cp_json = telemetry.get("commit_plan_json")
            if cp_json:
                try:
                    commit_plan = json.loads(cp_json)
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse commit_plan_json for trace {trace.id}: {e}")

        score_card = metadata.get("score_card")
        if not score_card:
            score_card = kwargs.get("score_card", {})
        if not score_card:
            score_card = telemetry.get("score_card", {})
        if not isinstance(score_card, dict):
            score_card = {}

        # We also need expected_output for evaluation_task (which is the user's accepted generated message)
        expected_output = input_data.get("final_commit_message")
        if not expected_output:
            expected_output = kwargs.get("generated_message")
        if not expected_output:
            expected_output = telemetry.get("generated_message")

        # Deterministic Gating: Reject if score_card shows failures
        all_pass = all(score_card.values()) if score_card else False
        if not all_pass:
            print(f"Skipping trace {trace.id}: score_card is missing, empty, or has failures")
            rejected_commits += 1
            continue

        if not commit_plan:
            print(f"Skipping trace {trace.id}: missing commit_plan")
            rejected_commits += 1
            continue
        if not diff:
            print(f"Skipping trace {trace.id}: missing diff.")
            rejected_commits += 1
            continue

        dataset_items.append(
            {
                "source_trace_id": trace.id,
                "diff_output": diff,
                "commit_plan": commit_plan,
                "score_card": score_card,
                "expected_output": expected_output,
            }
        )
        valid_commits += 1

    if dataset_items:
        print(f"Inserting {valid_commits} items into Opik dataset '{dataset_name}'...")
        try:
            dataset.insert(dataset_items)
        except Exception as e:
            print(f"Error inserting dataset items: {e}")

    print(f"Compiled dataset '{dataset_name}' with {valid_commits} valid commit records.")
    print(f"Rejected {rejected_commits} traces due to deterministic check failures.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile highly rated traces into an Opik dataset.")
    parser.add_argument("--project", default="gitCommitGenerator", help="Opik project name")
    parser.add_argument("--dataset", default="git-cg-golden-dataset", help="Target Opik dataset name")
    parser.add_argument("--threshold", type=float, default=0.8, help="Minimum feedback score to include")
    args = parser.parse_args()

    compile_dataset(args.project, args.dataset, args.threshold)
