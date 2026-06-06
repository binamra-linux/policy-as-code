"""AI Output Explainer — turns raw compliance violations into a readable report."""

import re
import logging
from collections import defaultdict

from ghascompliance.ai.prompts import EXPLAINER_SYSTEM_PROMPT
from ghascompliance.ai.providers.factory import get_provider

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.WARNING)

# Matches: "Dependabot Alert :: ghsa-xxx (critical) - pkg:pip/django"
_ALERT_RE = re.compile(
    r"(?:Dependabot|Code Scanning|Secret Scanning) Alert :: (\S+) \((\w+)\)"
    r"(?:\s*-\s*(.+))?$"
)


def _aggregate(violations: list) -> str:
    """
    Convert a flat list of raw violation messages into a compact grouped summary.
    Groups by package and severity so the model sees counts, not 58 raw lines.
    """
    # pkg -> severity -> count
    by_pkg: dict = defaultdict(lambda: defaultdict(int))

    for msg in violations:
        m = _ALERT_RE.search(msg)
        if m:
            _ghsa, severity, pkg_raw = m.group(1), m.group(2), m.group(3) or "unknown"
            # Normalise "pkg:pip/django" -> "django"
            pkg = pkg_raw.strip().split("/")[-1] if "/" in pkg_raw else pkg_raw.strip()
            by_pkg[pkg][severity.lower()] += 1

    if not by_pkg:
        return "\n".join(f"- {v}" for v in violations)

    lines = []
    for pkg, severities in sorted(by_pkg.items()):
        parts = [f"{sev}: {cnt}" for sev, cnt in sorted(severities.items())]
        lines.append(f"- {pkg}: {', '.join(parts)}")
    return "\n".join(lines)


def explain_results(
    repository: str,
    violations: list,
    total_errors: int,
    provider_name: str | None = None,
    model: str | None = None,
) -> str:
    """
    Generate a human-readable explanation of compliance violations.

    Args:
        repository:    GitHub repository (owner/repo).
        violations:    Raw violation log messages captured during the run.
        total_errors:  Total violation count reported by the tool.
        provider_name: AI provider (defaults to AI_PROVIDER env var or groq).
        model:         Optional model override.

    Returns:
        AI-generated report as a plain string.
    """
    provider = get_provider(provider_name, model)

    if not violations:
        user_message = (
            f"Repository: {repository}\n"
            f"Total unacceptable alerts: {total_errors}\n\n"
            "No individual violation details were captured."
        )
    else:
        aggregated = _aggregate(violations)
        user_message = (
            f"Repository: {repository}\n"
            f"Total violations: {total_errors}\n\n"
            f"Violations by package (severity: count):\n{aggregated}"
        )

    return provider.chat(
        [{"role": "user", "content": user_message}],
        EXPLAINER_SYSTEM_PROMPT,
    )
