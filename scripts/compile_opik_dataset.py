import glob
import json
import os


def compile_dataset():
    exports_dir = os.path.join("opik_exports", "thomo1318", "projects", "gitCommitGenerator")
    traces = glob.glob(os.path.join(exports_dir, "trace_*.json"))

    dataset_path = os.path.join("tests", "test_data", "opik_dataset.jsonl")
    os.makedirs(os.path.dirname(dataset_path), exist_ok=True)

    valid_commits = 0
    rejected_commits = 0
    with open(dataset_path, "w") as out_f:
        for t in traces:
            try:
                with open(t) as f:
                    data = json.load(f)

                trace_node = data.get("trace", {})

                # Check tags for final commit trace
                tags = trace_node.get("tags", [])
                if "git-cg-final" not in tags:
                    continue

                # Extract inputs and metadata
                trace_input = trace_node.get("input", {})
                trace_metadata = trace_node.get("metadata", {})

                diff = trace_metadata.get("diff_output") or trace_input.get("diff_output")
                commit_plan = trace_metadata.get("commit_plan")
                score_card = trace_metadata.get("score_card", {})

                # Deterministic Gating: Reject if score_card shows failures
                all_pass = all(score_card.values()) if score_card else False
                if not all_pass:
                    print(f"Rejecting {trace_node.get('id')} due to failed deterministic checks: {score_card}")
                    rejected_commits += 1
                    continue

                if not commit_plan or not diff:
                    continue

                # We have valid data that passed deterministic gating!
                record = {
                    "trace_id": trace_node.get("id"),
                    "diff": diff,
                    "commit_plan": commit_plan,
                    "score_card": score_card,
                }

                out_f.write(json.dumps(record) + "\n")
                valid_commits += 1

            except Exception as e:
                print(f"Skipping {t} due to error: {e}")

    print(f"Compiled dataset with {valid_commits} valid commit records.")
    print(f"Rejected {rejected_commits} commits due to deterministic check failures.")
    print(f"Saved to: {dataset_path}")


if __name__ == "__main__":
    compile_dataset()
