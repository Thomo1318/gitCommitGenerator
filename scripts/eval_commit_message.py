import json
import os

import opik
from opik.evaluation import evaluate
from opik.evaluation.metrics import GEval

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


def evaluation_task(item):
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
            if "output" in parsed:
                expected = parsed["output"]
        except json.JSONDecodeError:
            pass

    # Build the prompt
    system_prompt = build_system_prompt(diff_output, verbose=False)

    # Get client
    engine = os.environ.get("GIT_CG_ENGINE", "mtplx")
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

    return {"input": diff_output, "output": result_string, "expected_output": expected}


def main():
    dataset_name = "commit-message-eval"
    print(f"Starting evaluation on dataset: {dataset_name}")

    client = opik.Opik()
    dataset = client.get_dataset(name=dataset_name)

    evaluate(dataset=dataset, task=evaluation_task, scoring_metrics=[commit_quality_metric])


if __name__ == "__main__":
    main()
