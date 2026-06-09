"""AI-Driven Policy Recommender — analyses a repo's context and recommends a calibrated policy."""

import sys
import argparse
import logging
from typing import Optional

import requests

from ghascompliance.ai.prompts import RECOMMENDER_SYSTEM_PROMPT
from ghascompliance.ai.providers.factory import get_provider, SUPPORTED_PROVIDERS

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.WARNING)

_BANNER = """
╔══════════════════════════════════════════════════╗
║       AI Policy Recommender                      ║
║       Analyses your repo · Recommends policy     ║
╚══════════════════════════════════════════════════╝
"""


def _gh(path: str, token: str) -> object:
    """Make an authenticated GitHub API GET request."""
    resp = requests.get(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _count_by_severity(alerts: list) -> dict:
    counts: dict = {}
    for alert in alerts:
        sev = (
            alert.get("security_advisory", {}).get("severity")
            or alert.get("rule", {}).get("severity")
            or alert.get("severity", "unknown")
        ).lower()
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def fetch_repo_context(owner: str, repo: str, token: str) -> dict:
    """Fetch metadata and open alert counts from the GitHub API for a given repo."""
    ctx: dict = {"owner": owner, "repo": repo}

    try:
        meta = _gh(f"/repos/{owner}/{repo}", token)
        ctx["description"] = meta.get("description") or ""
        ctx["primary_language"] = meta.get("language") or "unknown"
        ctx["topics"] = meta.get("topics", [])
        ctx["open_issues"] = meta.get("open_issues_count", 0)
    except Exception:
        pass

    try:
        langs = _gh(f"/repos/{owner}/{repo}/languages", token)
        total = sum(langs.values()) or 1
        ctx["languages"] = {
            lang: round(bytes_ / total * 100, 1)
            for lang, bytes_ in sorted(langs.items(), key=lambda x: -x[1])
        }
    except Exception:
        ctx["languages"] = {}

    try:
        contributors = _gh(f"/repos/{owner}/{repo}/contributors?per_page=100&anon=false", token)
        ctx["contributor_count"] = len(contributors) if isinstance(contributors, list) else 0
    except Exception:
        ctx["contributor_count"] = 0

    try:
        dep_alerts = _gh(f"/repos/{owner}/{repo}/dependabot/alerts?state=open&per_page=100", token)
        ctx["dependabot_alerts"] = _count_by_severity(dep_alerts) if isinstance(dep_alerts, list) else {}
    except Exception:
        ctx["dependabot_alerts"] = {}

    try:
        cs_alerts = _gh(f"/repos/{owner}/{repo}/code-scanning/alerts?state=open&per_page=100", token)
        ctx["code_scanning_alerts"] = _count_by_severity(cs_alerts) if isinstance(cs_alerts, list) else {}
    except Exception:
        ctx["code_scanning_alerts"] = {}

    try:
        ss_alerts = _gh(f"/repos/{owner}/{repo}/secret-scanning/alerts?state=open&per_page=100", token)
        ctx["secret_scanning_open"] = len(ss_alerts) if isinstance(ss_alerts, list) else 0
    except Exception:
        ctx["secret_scanning_open"] = None

    return ctx


def _format_context(ctx: dict) -> str:
    """Turn the context dict into a structured prompt string for the AI."""
    lines = [f"Repository: {ctx['owner']}/{ctx['repo']}"]

    if ctx.get("description"):
        lines.append(f"Description: {ctx['description']}")

    if ctx.get("languages"):
        breakdown = ", ".join(f"{l} ({p}%)" for l, p in ctx["languages"].items())
        lines.append(f"Languages: {breakdown}")
    elif ctx.get("primary_language"):
        lines.append(f"Primary language: {ctx['primary_language']}")

    if ctx.get("contributor_count", 0) > 0:
        lines.append(f"Contributors: {ctx['contributor_count']} (team size proxy)")

    if ctx.get("topics"):
        lines.append(f"Topics: {', '.join(ctx['topics'])}")

    dep = ctx.get("dependabot_alerts", {})
    lines.append("")
    if dep:
        lines.append("Open Dependabot alerts:")
        for sev in ["critical", "high", "medium", "moderate", "low"]:
            if sev in dep:
                lines.append(f"  {sev}: {dep[sev]}")
    else:
        lines.append("Open Dependabot alerts: none detected")

    cs = ctx.get("code_scanning_alerts", {})
    if cs:
        lines.append("Open Code Scanning alerts:")
        for sev in ["error", "warning", "note"]:
            if sev in cs:
                lines.append(f"  {sev}: {cs[sev]}")
    else:
        lines.append("Open Code Scanning alerts: none detected")

    ss = ctx.get("secret_scanning_open")
    if ss is None:
        lines.append("Secret scanning: status unknown (may not be enabled)")
    elif ss == 0:
        lines.append("Secret scanning: enabled, 0 open alerts")
    else:
        lines.append(f"Secret scanning: {ss} open alert(s) — URGENT")

    return "\n".join(lines)


def recommend_policy(
    owner: str,
    repo: str,
    token: str,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple:
    """
    Fetch repo context and ask the AI for a recommended policy.

    Returns:
        (yaml_str, context_dict)
    """
    provider = get_provider(provider_name, model)
    ctx = fetch_repo_context(owner, repo, token)
    prompt = _format_context(ctx)
    yaml_str = provider.chat(
        [{"role": "user", "content": prompt}],
        RECOMMENDER_SYSTEM_PROMPT,
    )
    return yaml_str, ctx


def main(args=None) -> None:
    parser = argparse.ArgumentParser(
        prog="ghascompliance recommend-policy",
        description="Analyse a GitHub repo and recommend a calibrated security policy.",
    )
    parser.add_argument("--github-token", required=True, metavar="TOKEN")
    parser.add_argument("--github-repository", required=True, metavar="OWNER/REPO")
    parser.add_argument("--output", "-o", metavar="FILE", help="Save policy to file")
    parser.add_argument(
        "--provider", "-p",
        default=None,
        choices=SUPPORTED_PROVIDERS,
        metavar="PROVIDER",
    )
    parser.add_argument("--model", default=None, metavar="MODEL")

    parsed = parser.parse_args(args)
    print(_BANNER)

    if "/" not in parsed.github_repository:
        print("Error: --github-repository must be in owner/repo format")
        sys.exit(1)

    owner, repo = parsed.github_repository.split("/", 1)
    print(f"Analysing {owner}/{repo}...\n")

    try:
        yaml_str, ctx = recommend_policy(owner, repo, parsed.github_token, parsed.provider, parsed.model)
    except requests.HTTPError as exc:
        print(f"GitHub API error: {exc}")
        sys.exit(1)
    except EnvironmentError as exc:
        print(f"Provider error: {exc}")
        sys.exit(1)

    from ghascompliance.ai.validator import validate_policy_yaml
    is_valid, error, _ = validate_policy_yaml(yaml_str)
    if not is_valid:
        print(f"[Warning: policy failed schema validation: {error}]\n")

    if parsed.output:
        with open(parsed.output, "w") as fh:
            fh.write(yaml_str)
            if not yaml_str.endswith("\n"):
                fh.write("\n")
        print(f"Policy saved to: {parsed.output}")
    else:
        print("--- Recommended Policy ---\n")
        print(yaml_str)
        print("\n--- End of Policy ---")
