import glob
import json
import os


def compile_dataset():
    exports_dir = os.path.join("opik_exports", "thomo1318", "projects", "gitCommitGenerator")
    traces = glob.glob(os.path.join(exports_dir, "trace_*.json"))

    dataset_path = os.path.join("tests", "test_data", "opik_dataset.jsonl")
    os.makedirs(os.path.dirname(dataset_path), exist_ok=True)

    valid_commits = 0
    with open(dataset_path, "w") as out_f:
        for t in traces:
            try:
                with open(t) as f:
                    data = json.load(f)

                trace_node = data.get("trace", {})

                # Extract input
                trace_input = trace_node.get("input", {})
                if not trace_input:
                    continue
                diff = trace_input.get("diff_output")

                # Extract output
                trace_output = trace_node.get("output", {})
                if not trace_output:
                    continue

                output_data = trace_output.get("output", {})
                if not output_data:
                    continue

                primary_intent = output_data.get("primary_intent")
                if not primary_intent or not diff:
                    continue

                # We have valid data!
                record = {"trace_id": trace_node.get("id"), "diff": diff, "commit_plan": output_data}

                out_f.write(json.dumps(record) + "\n")
                valid_commits += 1

            except Exception as e:
                print(f"Skipping {t} due to error: {e}")

    print(f"Compiled dataset with {valid_commits} valid commit records.")
    print(f"Saved to: {dataset_path}")


if __name__ == "__main__":
    compile_dataset()
