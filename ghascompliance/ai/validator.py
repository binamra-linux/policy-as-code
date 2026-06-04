"""Validates AI-generated policy YAML against the existing Policy schema."""

import re
import logging
from typing import Tuple

import yaml

from ghascompliance.policy import Policy


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences if the model added them despite instructions."""
    text = text.strip()
    # Match ```yaml ... ``` or ``` ... ```
    match = re.match(r"^```(?:yaml)?\s*\n(.*?)```\s*$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def validate_policy_yaml(yaml_str: str) -> Tuple[bool, str, dict]:
    """
    Validate a YAML string against the policy schema.

    Returns:
        (is_valid, error_message, policy_dict)
        On success: (True, "", parsed_dict)
        On failure: (False, "<reason>", {})
    """
    yaml_str = strip_code_fences(yaml_str)

    if not yaml_str:
        return False, "Generated output was empty.", {}

    try:
        policy_dict = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        return False, f"YAML parse error: {exc}", {}

    if not isinstance(policy_dict, dict):
        return False, "Policy must be a YAML mapping (got a non-dict value).", {}

    # Re-use the existing Policy engine to catch schema violations.
    # Silence the Octokit/root logger during validation so AI mode output stays clean.
    try:
        logging.disable(logging.CRITICAL)
        policy = Policy(severity="error")
        policy.loadPolicy(policy_dict)
    except Exception as exc:
        return False, str(exc), {}
    finally:
        logging.disable(logging.NOTSET)

    return True, "", policy_dict


def extract_yaml_block(text: str) -> str:
    """
    Extract the first ```yaml ... ``` block from a string.
    Returns an empty string if none is found.
    """
    match = re.search(r"```(?:yaml)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""
