#!/usr/bin/env python
import argparse

import opik


def triage_traces(project_name: str):
    client = opik.Opik()

    print(f"=== Triaging Traces for Project: {project_name} ===")

    # Golden Traces (> 0.8)
    try:
        golden_traces = client.search_traces(
            project_name=project_name, filter_string="feedback_scores.user_acceptance > 0.8"
        )
        print(f"\nFound {len(golden_traces)} potential Golden traces (user_acceptance > 0.8).")
        for i, t in enumerate(golden_traces[:10]):
            score = next((s.value for s in (t.feedback_scores or []) if s.name == "user_acceptance"), "N/A")
            print(f"  [{i + 1}] Trace ID: {t.id} | Score: {score}")
        if len(golden_traces) > 10:
            print("  ... (truncated)")
    except Exception as e:
        print(f"Failed to fetch Golden traces: {e}")

    # Regression Traces (< 0.2)
    try:
        regression_traces = client.search_traces(
            project_name=project_name, filter_string="feedback_scores.user_acceptance < 0.2"
        )
        print(f"\nFound {len(regression_traces)} potential Regression traces (user_acceptance < 0.2).")
        for i, t in enumerate(regression_traces[:10]):
            score = next((s.value for s in (t.feedback_scores or []) if s.name == "user_acceptance"), "N/A")
            print(f"  [{i + 1}] Trace ID: {t.id} | Score: {score}")
        if len(regression_traces) > 10:
            print("  ... (truncated)")
    except Exception as e:
        print(f"Failed to fetch Regression traces: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Triage Opik traces based on feedback scores.")
    parser.add_argument("--project", default="gitCommitGenerator", help="Opik project name")
    args = parser.parse_args()

    triage_traces(args.project)
