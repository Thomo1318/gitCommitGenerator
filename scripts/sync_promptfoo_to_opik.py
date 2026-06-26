#!/usr/bin/env python
import argparse
import datetime
import json
import sys
from pathlib import Path

import sentry_sdk

import opik

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from git_cg.sentry_config import init_sentry


def parse_iso_timestamp(ts: str) -> datetime.datetime:
    """
    Convert an ISO 8601 timestamp string into a datetime value.

    Returns:
        datetime.datetime: The parsed datetime value, or the current UTC time if parsing fails.
    """
    try:
        # handle Z and fractional seconds
        if ts and isinstance(ts, str) and ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(ts)
    except Exception:
        return datetime.datetime.now(datetime.UTC)


def sync_results(file_path: str):
    """
    Sync Promptfoo evaluation results to Opik traces.

    Parameters:
        file_path (str): Path to the Promptfoo evaluation JSON file.
    """
    print(f"Loading Promptfoo results from {file_path}...")
    try:
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        sentry_sdk.capture_exception(exc)
        print(f"Error: Could not find {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        sentry_sdk.capture_exception(exc)
        print(f"Error: {file_path} is not valid JSON")
        sys.exit(1)

    client = opik.Opik()

    # Promptfoo JSON structure puts results in data["results"]["results"] (v2) or data["results"] (v1)
    results = data.get("results", {})
    if isinstance(results, dict):
        results = results.get("results", [])

    if not results:
        print("No results found in the JSON file.")
        sys.exit(0)

    print(f"Found {len(results)} test results. Syncing to Opik...")

    for result in results:
        prompt_raw = result.get("prompt", {}).get("raw", "")
        output = result.get("response", {}).get("output", "")
        success = result.get("success", False)

        # Mapping timestamps
        # Promptfoo usually provides timestamp and latencyMs
        timestamp_str = result.get("timestamp")
        raw_latency = result.get("latencyMs", 0)
        try:
            latency_ms = max(0.0, float(raw_latency or 0))
        except Exception:
            latency_ms = 0.0

        end_time = parse_iso_timestamp(timestamp_str) if timestamp_str else datetime.datetime.now(datetime.UTC)
        start_time = end_time - datetime.timedelta(milliseconds=latency_ms)

        try:
            trace = client.trace(
                name="promptfoo_eval",
                input={"prompt": prompt_raw, "vars": result.get("vars", {})},
                output={"output": output},
                start_time=start_time,
                end_time=end_time,
            )

            # Ship raw completion latencies and errors to Sentry
            sentry_sdk.add_breadcrumb(
                category="promptfoo_latency",
                message=f"Promptfoo evaluation latency: {latency_ms}ms",
                level="info",
                data={"latency_ms": latency_ms, "success": success},
            )
            if not success:
                sentry_sdk.add_breadcrumb(
                    category="promptfoo_evaluation_failure",
                    message=f"Promptfoo evaluation failed: {result.get('error', 'Assertion failed')}",
                    level="warning",
                )

            score = 1.0 if success else 0.0
            trace.log_feedback_score(name="feedback_score", value=score)
            trace.log_feedback_score(name="success", value=score)

            # Log assertion level scores if present
            grading = result.get("gradingResult")
            if grading and "componentResults" in grading:
                for comp in grading["componentResults"]:
                    assertion_type = comp.get("type", "custom")
                    trace.log_feedback_score(
                        name=f"assertion_{assertion_type}",
                        value=1.0 if comp.get("pass") else 0.0,
                        reason=comp.get("reason", ""),
                    )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            print(f"Warning: failed to sync one result to Opik: {exc}", file=sys.stderr)
            continue

    print("Sync complete! Traces are available in Opik.")


if __name__ == "__main__":
    init_sentry()
    parser = argparse.ArgumentParser(description="Sync Promptfoo evaluation results to Opik.")
    parser.add_argument("file", help="Path to promptfoo_results.json")
    args = parser.parse_args()

    try:
        sync_results(args.file)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise
    finally:
        sentry_sdk.flush(timeout=2.0)
