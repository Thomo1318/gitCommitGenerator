import json
import os

from opik.evaluation import evaluate
from opik.evaluation.metrics import GEval
from opik_metrics import FormatMetric

import opik
from git_cg.main import ENGINE_REGISTRY, build_system_prompt, generate_commit_message, get_ai_client

# Create a GEval metric to evaluate the commit messages using an LLM judge
commit_quality_metric = GEval(
    name="CommitMessageQuality",
    task_introduction="You are an expert software engineer reviewing a generated commit message.",
    evaluation_criteria="""
Evaluate the Generated Commit Message based on how well it captures the changes in the Diff Context and whether it aligns with the Expected Commit Message's core intent.
Provide a score from 0.0 to 1.0, where 1.0 means it's an excellent, accurate commit message, and 0.0 means it completely misses the point.
""",
)


_generation_cache = {}


def evaluation_task(item):
    """
    Generate a commit message from a diff and return the evaluation payload.

    Parameters:
        item: An evaluation item containing 'diff_output' and 'expected_output' fields. Accepts either a dict or object with these attributes. The 'expected_output' field may be a string, JSON string, or dict containing an 'output' key.

    Returns:
        dict: Evaluation payload with keys 'input' (the diff), 'output' (the generated commit message), and 'expected_output' (the normalised expected message).
    """
    print("Starting evaluation_task for item...")
    # Extract data, handling both dict and object formats
    if isinstance(item, dict):
        diff_output = item.get("diff_output", "")
        expected = item.get("expected_output", "")
    else:
        diff_output = getattr(item, "diff_output", "")
        expected = getattr(item, "expected_output", "")

    # If expected_output is a JSON string or dict with 'output' key, extract it
    if isinstance(expected, dict) and "output" in expected:
        expected = expected["output"]
    elif isinstance(expected, str):
        try:
            parsed = json.loads(expected)
            if isinstance(parsed, dict) and "output" in parsed:
                expected = parsed["output"]
        except json.JSONDecodeError:
            pass

    # Use cache if already generated for this diff
    if diff_output in _generation_cache:
        print("Using cached generation for Tier-2 evaluation.")
        result_string = _generation_cache[diff_output]
        return {"input": diff_output, "output": result_string, "expected_output": expected}

    # Build the prompt
    system_prompt = build_system_prompt(diff_output, verbose=False)

    # Get client
    engine = os.environ.get("GIT_CG_ENGINE", "mtplx")
    if engine:
        engine = engine.strip()
    if not engine:  # Handle empty or whitespace-only string
        engine = "mtplx"
    client = get_ai_client(engine)

    # Get model name
    engine_config = ENGINE_REGISTRY.get(engine.lower())
    prefix = engine_config.prefix if engine_config else "OMLX"
    model_name = os.environ.get(f"{prefix}_MODEL", os.environ.get("OMLX_MODEL", "default"))

    # Generate
    print(f"Generating commit for item with model {model_name}...")
    commit_plan = generate_commit_message(
        client=client, diff_output=diff_output, model_name=model_name, system_prompt=system_prompt
    )

    result_string = commit_plan.render()
    print(f"Generation complete. Generated message length: {len(result_string)}")

    _generation_cache[diff_output] = result_string

    return {"input": diff_output, "output": result_string, "expected_output": expected}


def main():
    """
    Run the Opik evaluation pipeline to score generated commit messages against format and quality standards.
    """
    dataset_name = "commit-message-eval"
    print(f"Starting evaluation on dataset: {dataset_name}")

    client = opik.Opik()
    dataset = client.get_dataset(name=dataset_name)

    format_metric = FormatMetric()

    print("Running Tier-1 evaluation (Format validation)...")
    eval_results = evaluate(dataset=dataset, task=evaluation_task, scoring_metrics=[format_metric])

    # Ensure format validation passes before proceeding to semantic evaluation
    all_passed = True
    for test_result in getattr(eval_results, "test_results", []):
        for metric_result in getattr(test_result, "score_results", []):
            if (
                getattr(metric_result, "name", "") == "CommitFormatQuality"
                and getattr(metric_result, "value", 0.0) < 1.0
            ):
                all_passed = False
                break
        if not all_passed:
            break

    if not all_passed:
        print("Tier-1 format validation failed for one or more items. Aborting Tier-2 semantic evaluation.")
        return

    print("Tier-1 format validation passed. Running Tier-2 semantic evaluation...")
    evaluate(dataset=dataset, task=evaluation_task, scoring_metrics=[commit_quality_metric])


if __name__ == "__main__":
    main()
