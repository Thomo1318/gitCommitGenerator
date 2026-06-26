import contextlib
import importlib.metadata
import os

import sentry_sdk


def init_sentry():
    """
    Initialise Sentry telemetry for the application.

    Sentry setup can be disabled by setting ``GIT_CG_DISABLE_SENTRY`` to ``"1"``. When enabled, captured git diff output in Sentry event contexts is scrubbed before sending.
    """
    if os.environ.get("GIT_CG_DISABLE_SENTRY", "0") == "1":
        return

    try:
        version = importlib.metadata.version("gitcommitgenerator")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"

    def scrub_data(event, hint):
        # Prevent massive diffs from overflowing the 8kb context limit or leaking source code
        """
        Scrub git diff output from a Sentry event.

        Parameters:
                event: The event payload to sanitise.

        Returns:
                The event payload with any git_cg diff output replaced with "[SCRUBBED]".
        """
        if "contexts" in event and "git_cg" in event["contexts"] and "diff_output" in event["contexts"]["git_cg"]:
            event["contexts"]["git_cg"]["diff_output"] = "[SCRUBBED]"

        # Scrub local variables that could contain large strings, source code, paths or PII
        if "exception" in event and "values" in event["exception"]:
            for exc in event["exception"]["values"]:
                if "stacktrace" in exc and "frames" in exc["stacktrace"]:
                    for frame in exc["stacktrace"]["frames"]:
                        if "vars" in frame:
                            for var_name in [
                                "diff_output",
                                "system_prompt",
                                "prompt",
                                "messages",
                                "result_string",
                                "commit_msg_file",
                                "git_dir",
                                "cwd",
                            ]:
                                if var_name in frame["vars"]:
                                    frame["vars"][var_name] = "[SCRUBBED]"

        return event

    with contextlib.suppress(Exception):
        sentry_sdk.init(
            dsn=os.environ.get("SENTRY_DSN"),
            environment=os.environ.get("SENTRY_ENVIRONMENT", "local"),
            release=f"gitCommitGenerator@{version}",
            send_default_pii=False,
            before_send=scrub_data,
            traces_sample_rate=0.0,
        )
