#!/usr/bin/env python
import argparse
import os
import sys
from typing import Any

import opik
from opik.evaluation import evaluate

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import existing metrics and the task runner
from eval_commit_message import commit_quality_metric, evaluation_task
from opik_metrics import FormatMetric


def run_test_suite(dataset_name: str, metric_name: str):
    client = opik.Opik()

    print("=== Setting up Test Suite ===")
    print(f"Dataset: {dataset_name}")
    print(f"Metric:  {metric_name}")

    try:
        dataset = client.get_dataset(name=dataset_name)
    except Exception as e:
        print(f"Error: Dataset '{dataset_name}' could not be fetched. Ensure it exists in Opik Cloud. Details: {e}")
        return

    # Choose metrics based on the argument
    metrics: list[Any] = []
    if metric_name == "git-cg-commit-quality":
        metrics = [FormatMetric(), commit_quality_metric]
    elif metric_name == "format-only":
        metrics = [FormatMetric()]
    elif metric_name == "semantic-only":
        metrics = [commit_quality_metric]
    else:
        print(f"Unknown metric suite: {metric_name}")
        return

    print("Executing evaluation...")
    try:
        evaluate(
            dataset=dataset,
            task=evaluation_task,
            scoring_metrics=metrics,
            experiment_config={"metric_suite": metric_name},
        )
        print("Evaluation completed successfully.")
    except Exception as e:
        print(f"Evaluation failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Opik test suites by binding datasets to GEval metrics.")
    parser.add_argument("--dataset", default="git-cg-golden-dataset", help="Target Opik dataset name")
    parser.add_argument(
        "--metric",
        default="git-cg-commit-quality",
        help="Metric suite to apply (git-cg-commit-quality, format-only, semantic-only)",
    )
    args = parser.parse_args()

    run_test_suite(args.dataset, args.metric)
