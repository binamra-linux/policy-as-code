"""AI-assisted policy writer: single-shot and interactive modes."""

import sys
import argparse

import yaml

from ghascompliance.ai.generator import (
    DEFAULT_MODEL,
    generate_single_shot,
    generate_with_error_fix,
    chat_turn,
)
from ghascompliance.ai.validator import validate_policy_yaml, extract_yaml_block

_BANNER = """
╔══════════════════════════════════════════════════╗
║       AI-Assisted Policy Writer                  ║
║       Powered by Claude (Anthropic)              ║
╚══════════════════════════════════════════════════╝
"""

_INTERACTIVE_INTRO = """
Welcome to the interactive policy writer.
I'll ask you a few questions to understand your security requirements,
then generate a policy YAML file you can use directly.

Type 'quit' or press Ctrl+C at any time to exit without saving.
"""


def _write_output(yaml_str: str, output_path: str | None) -> None:
    if output_path:
        with open(output_path, "w") as fh:
            fh.write(yaml_str)
            if not yaml_str.endswith("\n"):
                fh.write("\n")
        print(f"\nPolicy saved to: {output_path}")
    else:
        print("\n--- Generated Policy ---\n")
        print(yaml_str)
        print("\n--- End of Policy ---")


def run_single_shot(
    description: str,
    output: str | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
) -> int:
    """
    Generate a policy from a description string.
    Returns 0 on success, 1 on failure.
    """
    print(f"Generating policy for: {description!r}")
    print(f"Model: {model}\n")

    yaml_str = ""
    last_error = ""

    for attempt in range(1, max_retries + 1):
        if attempt == 1:
            yaml_str = generate_single_shot(description, model=model)
        else:
            print(f"Retrying (attempt {attempt}/{max_retries}) after validation error...")
            yaml_str = generate_with_error_fix(
                description, yaml_str, last_error, model=model
            )

        is_valid, error, policy_dict = validate_policy_yaml(yaml_str)

        if is_valid:
            print("Validation passed.")
            _write_output(yaml_str, output)
            return 0

        last_error = error
        print(f"Validation failed: {error}")

    print(
        f"\nFailed to generate a valid policy after {max_retries} attempts.\n"
        f"Last error: {last_error}"
    )
    return 1


def run_interactive(
    output: str | None = None,
    model: str = DEFAULT_MODEL,
) -> int:
    """
    Multi-turn conversation to build a policy step by step.
    Returns 0 on success, 1 if the user cancelled.
    """
    print(_INTERACTIVE_INTRO)

    messages = []
    last_valid_yaml = ""

    # Seed the conversation: Claude opens with the first question
    opening = chat_turn(
        [{"role": "user", "content": "Hello, I want to create a security policy."}],
        model=model,
    )
    print(f"Assistant: {opening}\n")
    messages.append({"role": "user", "content": "Hello, I want to create a security policy."})
    messages.append({"role": "assistant", "content": opening})

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled. No policy was saved.")
            return 1

        if user_input.lower() in ("quit", "exit", "q"):
            print("Exiting. No policy was saved.")
            return 1

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        response = chat_turn(messages, model=model)
        messages.append({"role": "assistant", "content": response})

        # Check if Claude is signalling completion
        if "POLICY_FINALIZED" in response:
            if last_valid_yaml:
                _write_output(last_valid_yaml, output)
                return 0
            else:
                print("Assistant: (no valid policy was generated yet — please continue.)\n")
                continue

        # Check if a YAML block was generated in this response
        yaml_block = extract_yaml_block(response)
        if yaml_block:
            is_valid, error, _ = validate_policy_yaml(yaml_block)
            if is_valid:
                last_valid_yaml = yaml_block
                clean_response = response
                print(f"\nAssistant: {clean_response}\n")
            else:
                print(f"\nAssistant: {response}")
                print(
                    f"\n[Note: the generated YAML has a validation issue: {error}. "
                    "You can ask me to fix it.]\n"
                )
        else:
            print(f"\nAssistant: {response}\n")


def main(args: list | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ghascompliance generate-policy",
        description="Generate a security policy YAML using AI (Claude).",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--description",
        "-d",
        metavar="TEXT",
        help="Natural language description of the desired policy (single-shot mode).",
    )
    mode_group.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Start an interactive conversation to build the policy step by step.",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Save the generated policy to this file (default: print to stdout).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        metavar="MODEL",
        help=f"Claude model to use (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        metavar="N",
        help="Max validation retry attempts in single-shot mode (default: 3).",
    )

    parsed = parser.parse_args(args)

    print(_BANNER)

    if parsed.interactive:
        sys.exit(run_interactive(output=parsed.output, model=parsed.model))
    elif parsed.description:
        sys.exit(
            run_single_shot(
                description=parsed.description,
                output=parsed.output,
                model=parsed.model,
                max_retries=parsed.max_retries,
            )
        )
    else:
        parser.print_help()
        sys.exit(0)
