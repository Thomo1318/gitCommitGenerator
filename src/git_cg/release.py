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
    prefix = "v" if version.startswith("v") else ""
    v_str = version.lstrip("v")
    try:
        ver = semver.VersionInfo.parse(v_str)

        # Rule 4: If major is 0, a breaking change should bump minor instead
        if ver.major == 0 and bump_type == "MAJOR":
            bump_type = "MINOR"

        if pre_release:
            if bump_type == "MAJOR":
                ver = ver.bump_major().replace(prerelease=f"{pre_release}.0")
            elif bump_type == "MINOR":
                ver = ver.bump_minor().replace(prerelease=f"{pre_release}.0")
            elif bump_type == "PATCH":
                ver = ver.bump_patch().replace(prerelease=f"{pre_release}.0")
            elif bump_type == "PRERELEASE" or bump_type == "NONE":
                if ver.prerelease and ver.prerelease.split(".")[0] == pre_release:
                    ver = ver.bump_prerelease(token=pre_release)
                else:
                    ver = ver.replace(prerelease=f"{pre_release}.0")
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
    Inject updated version strings into files according to configured version-injection strategies.

    Reads each given file and, when a matching strategy is found in `sop_data["specifications_and_standards"]["version_injection_matrix"]["strategies"]`, replaces the first version occurrence using the specified strategy and the provided `bump_type`. Modified files are written back unless `dry_run` is True.

    Parameters:
        files (list[str]): File paths to scan for injectable version strings.
        bump_type (str): One of "MAJOR", "MINOR", "PATCH" or "NONE"; no action is taken when "NONE" and no pre_release.
        sop_data (dict): SOP configuration containing the version injection matrix under
            `specifications_and_standards.version_injection_matrix.strategies`.
        dry_run (bool): If True, perform detection and logging only; do not write changes to disk.
        verbose (bool): If True, print detailed messages about injections and errors.
        pre_release (str | None): Optional pre-release identifier to append/bump.
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

            if modified and not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
        except Exception as e:
            if verbose:
                console.print(f"Could not inject version into {filepath}: {e}")


def group_commits_for_changelog(commits: list[str], gitmoji_matrix: list) -> dict[str, list[str]]:
    """
    Map commit entries to changelog groups based on explicit trailers or gitmoji metadata.

    Parses each raw commit string (expected to contain the subject and an optional body separated by '---COMMIT_BODY---') and assigns the commit subject to one or more changelog groups. If the commit body contains a `Changelog-Groups:` trailer, the listed comma-separated groups (trimmed) are used. Otherwise, the function falls back to legacy matching: it compares the commit subject against entries in `gitmoji_matrix` (matching either the `emoji` substring or the `:{code}:` token) and uses the entry's `changelog_group` value; if no entry matches, the subject is placed in the "Miscellaneous" group.

    Parameters:
        commits (list[str]): Raw commit strings where the subject is before `---COMMIT_BODY---` and the optional body after it.
        gitmoji_matrix (list): List of mapping entries describing gitmoji metadata; each entry may contain `emoji`, `code`, and `changelog_group` keys used for legacy grouping.

    Returns:
        dict[str, list[str]]: Mapping of changelog group name to a list of commit subjects assigned to that group.
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


def execute_release(dry_run: bool, verbose: bool, pre_release: str | None = None):
    """
    Prepare a release by analysing commits since the last Git tag, computing the required SemVer bump, optionally injecting the new version into files, and prepending a generated changelog section to CHANGELOG.md.

    When dry_run is True, no files are written; when False, modified files may be updated and CHANGELOG.md will be prepended. This function does not create Git tags or perform commits.

    Parameters:
        dry_run (bool): If True, perform a simulation without writing files or updating CHANGELOG.md.
        verbose (bool): If True, emit additional diagnostic output to the console.
        pre_release (str | None): Optional pre-release identifier (e.g., 'alpha', 'rc').
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
