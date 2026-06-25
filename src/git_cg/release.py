import os
import re
import subprocess
from collections import defaultdict

import semver
from rich.console import Console
from rich.panel import Panel

from git_cg.sop import load_sop

console = Console()


def get_sop_data():
    return load_sop()


def get_last_tag() -> str:
    try:
        tag = (
            subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
        return tag
    except subprocess.CalledProcessError:
        return ""


def get_commits_since(tag: str) -> list[str]:
    try:
        if tag:
            log_output = subprocess.check_output(
                ["git", "log", f"{tag}..HEAD", "--pretty=format:%s---COMMIT_BODY---%b---COMMIT_DELIM---"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8")
        else:
            log_output = subprocess.check_output(
                ["git", "log", "--pretty=format:%s---COMMIT_BODY---%b---COMMIT_DELIM---"], stderr=subprocess.DEVNULL
            ).decode("utf-8")

        commits = [line for line in log_output.split("---COMMIT_DELIM---") if line.strip()]
        return commits
    except subprocess.CalledProcessError:
        return []


def get_modified_files_since(tag: str) -> list[str]:
    try:
        # If no tag, get all files currently tracked
        cmd = ["git", "diff", "--name-only", f"{tag}..HEAD"] if tag else ["git", "ls-files"]
        files = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").split("\n")
        return [f for f in files if f.strip() and os.path.exists(f)]
    except subprocess.CalledProcessError:
        return []


def parse_commit_impact(commit_string: str, gitmoji_matrix: list) -> str:
    parts = commit_string.split("---COMMIT_BODY---", 1)
    subject = parts[0]
    body = parts[1] if len(parts) > 1 else ""

    # 1. Prefer machine-readable trailer from CommitPlan
    trailer_match = re.search(r"^SemVer-Impact:\s*(MAJOR|MINOR|PATCH|NONE)", body, flags=re.MULTILINE)
    if trailer_match:
        return trailer_match.group(1).upper()

    # 2. Check for manual breaking change indicators
    if "BREAKING CHANGE:" in body or "BREAKING CHANGE:" in subject:
        return "MAJOR"

    # 3. Legacy fallback: Regex on header cc_type and breaking indicator
    match = re.search(r"^[^\s]+\s+([a-z]+)(?:\(.*?\)?)?(!?):", subject)
    if match:
        cc_type = match.group(1)
        is_breaking = match.group(2) == "!"
        if is_breaking:
            return "MAJOR"

        for entry in gitmoji_matrix:
            if entry.get("cc_type") == cc_type:
                return entry.get("semver_impact", "NONE")

    # 4. Legacy fallback: Check emojis directly
    for entry in gitmoji_matrix:
        if entry.get("emoji") in subject:
            return entry.get("semver_impact", "NONE")

    return "NONE"


def calculate_global_bump(commits: list[str], gitmoji_matrix: list) -> str:
    """
    Determine the highest SemVer bump required by the given commits.

    Parameters:
        commits (list[str]): Commit strings to evaluate.
        gitmoji_matrix (list): Metadata used to interpret commit impact.

    Returns:
        str: "MAJOR", "MINOR", "PATCH", or "NONE", depending on the highest impact found.
    """
    highest_bump = "NONE"
    for commit in commits:
        impact = parse_commit_impact(commit, gitmoji_matrix)
        if impact == "MAJOR":
            return "MAJOR"
        elif impact == "MINOR":
            highest_bump = "MINOR"
        elif impact == "PATCH" and highest_bump == "NONE":
            highest_bump = "PATCH"
    return highest_bump


def bump_version_string(version: str, bump_type: str, pre_release: str | None = None) -> str:
    """
    Update a semantic version string.

    Parameters:
        version (str): The version string to update.
        bump_type (str): The version increment to apply.
        pre_release (str | None): Pre-release identifier to apply or advance.

    Returns:
        str: The updated version string, or the original version if parsing or bumping fails.
    """
    prefix = "v" if version.startswith("v") else ""
    v_str = version.lstrip("v")
    try:
        ver = semver.VersionInfo.parse(v_str)

        # Rule 4: If major is 0, a breaking change should bump minor instead
        if ver.major == 0 and bump_type == "MAJOR":
            bump_type = "MINOR"

        if pre_release:
            if bump_type == "MAJOR":
                ver = ver.bump_major().replace(prerelease=f"{pre_release}.1")
            elif bump_type == "MINOR":
                ver = ver.bump_minor().replace(prerelease=f"{pre_release}.1")
            elif bump_type == "PATCH":
                ver = ver.bump_patch().replace(prerelease=f"{pre_release}.1")
            elif bump_type == "PRERELEASE" or bump_type == "NONE":
                if ver.prerelease:
                    if ver.prerelease.split(".")[0] == pre_release:
                        ver = ver.bump_prerelease(token=pre_release)
                    else:
                        ver = ver.replace(prerelease=f"{pre_release}.1")
                else:
                    # SemVer Rule 9: transitioning from stable to prerelease requires bumping patch
                    ver = ver.bump_patch().replace(prerelease=f"{pre_release}.1")
        else:
            if ver.prerelease and bump_type in ("NONE", "PRERELEASE", "PATCH"):
                ver = ver.finalize_version()
            elif bump_type == "MAJOR":
                ver = ver.bump_major()
            elif bump_type == "MINOR":
                ver = ver.bump_minor()
            elif bump_type == "PATCH":
                ver = ver.bump_patch()

        return f"{prefix}{ver!s}"
    except Exception as e:
        console.print(
            f"[yellow]Failed to parse or bump version '{version}' with semver: {e}. Returning unmodified.[/yellow]"
        )
        return version


def inject_file_versions(
    files: list[str], bump_type: str, sop_data: dict, dry_run: bool, verbose: bool, pre_release: str | None = None
):
    """
    Inject bumped version strings into matching files.

    Updates the first version string found in each file when its extension matches a configured injection strategy.

    Parameters:
        files (list[str]): File paths to scan.
        bump_type (str): The SemVer bump to apply.
        sop_data (dict): SOP configuration containing the version injection matrix.
        dry_run (bool): When true, do not write changes to disk.
        verbose (bool): When true, print injection details and file-level errors.
        pre_release (str | None): Optional pre-release identifier to apply or advance.
    """
    if bump_type == "NONE" and not pre_release:
        return

    strategies = (
        sop_data.get("specifications_and_standards", {}).get("version_injection_matrix", {}).get("strategies", {})
    )
    if not strategies:
        return

    for filepath in files:
        _, ext = os.path.splitext(filepath)

        # Find matching strategy
        strategy = None
        for s in strategies.values():
            if ext in s.get("extensions", []):
                strategy = s
                break

        if not strategy:
            continue

        method = strategy.get("method")

        try:
            with open(filepath, encoding="utf-8") as f:
                file_content = f.read()

            modified = False

            def replacer(match, current_filepath=filepath):
                """
                Update a matched version string and report the change.

                Parameters:
                        match: The regex match object.
                        current_filepath: The file currently being processed.

                Returns:
                        str: The replacement text for the matched version.
                """
                nonlocal modified
                old_v = match.group(2)
                new_v = bump_version_string(old_v, bump_type, pre_release=pre_release)
                if old_v != new_v:
                    modified = True
                    if verbose or dry_run:
                        console.print(
                            f"Bumped [cyan]{current_filepath}[/cyan]: [red]{old_v}[/red] -> [green]{new_v}[/green]"
                        )
                return match.group(1) + new_v + match.group(3)

            new_content = file_content
            if method in ("root_key", "json"):
                # Matches: "version": "1.0.0"
                new_content = re.sub(r'("version"\s*:\s*")([^"]+)(")', replacer, file_content, count=1)
            elif method in ("hash_comment", "header_comment"):
                # Matches: # version: v2.0.0
                new_content = re.sub(
                    r"(#\s*version:\s*)(v?\d+\.\d+\.\d+)(\s*)", replacer, file_content, count=1, flags=re.IGNORECASE
                )
            elif method == "slash_comment":
                # Matches: // version: v1.0.0
                new_content = re.sub(
                    r"(//\s*version:\s*)(v?\d+\.\d+\.\d+)(\s*)", replacer, file_content, count=1, flags=re.IGNORECASE
                )
            elif method == "block_comment":
                # Matches: <!-- version: v1.0.0 -->
                new_content = re.sub(
                    r"(<!--\s*version:\s*)(v?\d+\.\d+\.\d+)(\s*-->)",
                    replacer,
                    file_content,
                    count=1,
                    flags=re.IGNORECASE,
                )
            elif method == "python_variable":
                # Matches: __version__ = "1.0.0" or __version__ = '1.0.0'
                new_content = re.sub(
                    r'(__version__\s*=\s*[\'"])(v?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)([\'"])',
                    replacer,
                    file_content,
                    count=1,
                )

            if modified and not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
        except Exception as e:
            if verbose:
                console.print(f"Could not inject version into {filepath}: {e}")


def group_commits_for_changelog(commits: list[str], gitmoji_matrix: list) -> dict[str, list[str]]:
    """
    Group commit subjects into changelog sections.

    Uses the `Changelog-Groups:` trailer when present to place a commit subject in one or more sections. Otherwise, falls back to the first matching gitmoji changelog group, or `Miscellaneous` when no match is found.

    Parameters:
        commits (list[str]): Raw commit strings containing a subject and optional body.
        gitmoji_matrix (list): Gitmoji metadata used to resolve legacy changelog groups.

    Returns:
        dict[str, list[str]]: Changelog groups mapped to their commit subjects.
    """
    changelog_groups = defaultdict(list)
    for commit in commits:
        parts = commit.split("---COMMIT_BODY---", 1)
        subject = parts[0]
        body = parts[1] if len(parts) > 1 else ""

        # Prefer machine-readable trailer for mixed-commit support
        trailer_match = re.search(r"^Changelog-Groups:\s*(.+)$", body, flags=re.MULTILINE)
        if trailer_match:
            # Commit can belong to multiple groups if it had secondary intents
            groups = [g.strip() for g in trailer_match.group(1).split(",")]
            for g in groups:
                if g:
                    changelog_groups[g].append(subject)
            continue

        # Legacy fallback logic
        group = "Miscellaneous"
        for entry in gitmoji_matrix:
            if entry.get("emoji") in subject or f":{entry.get('code')}:" in subject:
                group = entry.get("changelog_group", "Miscellaneous")
                break
        changelog_groups[group].append(subject)

    return changelog_groups


def validate_release(new_tag: str) -> bool:
    """Ensure the new tag does not already exist locally or remotely."""
    try:
        subprocess.check_call(["git", "fetch", "--tags"], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        console.print(
            "[yellow]Warning: Could not fetch tags from remote (offline?). Falling back to local uniqueness check.[/yellow]"
        )

    try:
        existing_tags = (
            subprocess.check_output(["git", "tag", "-l"], stderr=subprocess.DEVNULL).decode("utf-8").splitlines()
        )
        if new_tag in existing_tags:
            console.print(
                f"[bold red]Validation Error:[/bold red] Git tag '{new_tag}' already exists locally. Release aborted to prevent collision."
            )
            return False
    except subprocess.CalledProcessError:
        pass

    return True


def execute_release(dry_run: bool, verbose: bool, pre_release: str | None = None):
    """
    Prepare a release from the commits since the last Git tag.

    Determines the required SemVer bump, updates configured version fields, and prepends a generated changelog entry to CHANGELOG.md unless dry run mode is enabled. If no version change is needed, the release is skipped.

    Parameters:
        dry_run (bool): Simulate the release without writing files.
        verbose (bool): Emit additional progress output.
        pre_release (str | None): Optional pre-release identifier to apply to the generated version.
    """
    sop_data = get_sop_data()
    gitmoji_matrix = sop_data.get("gitmoji_reference_matrix", [])

    last_tag = get_last_tag()
    commits = get_commits_since(last_tag)

    if verbose:
        console.log(f"Found {len(commits)} commits since tag '{last_tag}'.")

    bump_type = calculate_global_bump(commits, gitmoji_matrix)

    is_prerelease = False
    try:
        if last_tag:
            is_prerelease = bool(semver.VersionInfo.parse(last_tag.lstrip("v")).prerelease)
    except Exception:
        pass

    if bump_type == "NONE" and not pre_release and not is_prerelease:
        console.print("[yellow]No changes warrant a SemVer bump. Aborting release.[/yellow]")
        return

    console.print(f"[bold green]Calculated Release Impact:[/bold green] {bump_type}")

    if not last_tag and pre_release:
        try:
            semver.VersionInfo.parse(f"0.1.0-{pre_release}.0")
        except Exception:
            console.print(
                f"[bold red]Validation Error:[/bold red] Invalid pre-release identifier '{pre_release}'. Must comply with SemVer 2.0.0."
            )
            return

    new_tag = (
        bump_version_string(last_tag, bump_type, pre_release=pre_release)
        if last_tag
        else (f"v0.1.0-{pre_release}.0" if pre_release else "v0.1.0")
    )
    if not new_tag.startswith("v"):
        new_tag = "v" + new_tag

    if new_tag == last_tag:
        console.print("[yellow]Calculated version is identical to the current tag. Aborting release.[/yellow]")
        return

    if not validate_release(new_tag):
        return

    console.print(f"[bold green]Next Version:[/bold green] {new_tag}")

    # File injection (per file)
    modified_files = get_modified_files_since(last_tag)
    if verbose:
        console.log(f"Scanning {len(modified_files)} modified files for version headers...")

    inject_file_versions(modified_files, bump_type, sop_data, dry_run, verbose, pre_release=pre_release)

    # Generate Changelog

    changelog_groups = group_commits_for_changelog(commits, gitmoji_matrix)

    # Format changelog
    changelog_str = f"## {new_tag}\n\n"
    for group, subjects in changelog_groups.items():
        changelog_str += f"### {group}\n"
        for sub in subjects:
            changelog_str += f"- {sub}\n"
        changelog_str += "\n"

    if dry_run or verbose:
        console.print(Panel(changelog_str, title=f"Generated Changelog for {new_tag}"))

    if not dry_run:
        # Prepend to CHANGELOG.md
        changelog_path = "CHANGELOG.md"
        old_content = ""
        if os.path.exists(changelog_path):
            with open(changelog_path) as f:
                old_content = f.read()
        with open(changelog_path, "w") as f:
            f.write(changelog_str + old_content)
        console.print("[bold green]CHANGELOG.md updated.[/bold green]")

        # We don't automatically tag here as user requested to just prepare it
        console.print(
            f"[bold yellow]Files modified. Run `git add . && git commit -m '🔖 release: {new_tag}'` and `git tag {new_tag}` to finish.[/bold yellow]"
        )
