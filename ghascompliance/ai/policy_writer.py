"""AI-assisted policy writer: single-shot and interactive modes."""

import sys
import logging
import argparse

# Third-party SDK loggers (httpx, groq, google) are noisy — suppress them.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)

from ghascompliance.ai.generator import (
    generate_single_shot,
    generate_with_error_fix,
    chat_turn,
)
from ghascompliance.ai.providers.factory import get_provider, SUPPORTED_PROVIDERS
from ghascompliance.ai.validator import validate_policy_yaml, extract_yaml_block

_BANNER = """
╔══════════════════════════════════════════════════╗
║       AI-Assisted Policy Writer                  ║
║       policy-as-code + AI layer                  ║
╚══════════════════════════════════════════════════╝
"""

_INTERACTIVE_INTRO = """
Welcome to the interactive policy writer.
The AI will ask up to 3 short questions, then generate your policy.

Commands:
  generate  — force policy generation immediately
  quit      — exit without saving
  Ctrl+C    — exit without saving
"""

# After this many user answers, automatically inject "generate now" into the conversation.
_MAX_TURNS_BEFORE_GENERATE = 3


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
    provider_name: str | None = None,
    model: str | None = None,
    max_retries: int = 3,
) -> int:
    """Generate a policy from a description. Returns 0 on success, 1 on failure."""
    provider = get_provider(provider_name, model)
    print(f"Provider : {provider.name}  |  Model: {provider.model}")
    print(f"Request  : {description!r}\n")

    yaml_str = ""
    last_error = ""

    for attempt in range(1, max_retries + 1):
        if attempt == 1:
            yaml_str = generate_single_shot(description, provider)
        else:
            print(f"Retrying (attempt {attempt}/{max_retries}) after validation error...")
            yaml_str = generate_with_error_fix(description, yaml_str, last_error, provider)

        is_valid, error, _ = validate_policy_yaml(yaml_str)

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


def _prompt_save(yaml_str: str, output: str | None) -> bool:
    """Ask the user to confirm saving. Returns True if saved."""
    print("\n" + "-" * 52)
    print(yaml_str)
    print("-" * 52)
    try:
        answer = input("\nSave this policy? [y = yes / anything else = adjust]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return False
    if answer in ("y", "yes", ""):
        _write_output(yaml_str, output)
        return True
    return False


def run_interactive(
    output: str | None = None,
    provider_name: str | None = None,
    model: str | None = None,
) -> int:
    """Multi-turn conversation to build a policy. Returns 0 on success, 1 if cancelled."""
    provider = get_provider(provider_name, model)
    print(_INTERACTIVE_INTRO)
    print(f"Provider: {provider.name}  |  Model: {provider.model}\n")

    messages = []
    last_valid_yaml = ""
    user_turn_count = 0

    # Seed: user sends a greeting; Claude opens with the first question.
    seed = "Hello, I want to create a security policy."
    opening = chat_turn([{"role": "user", "content": seed}], provider)
    print(f"Assistant: {opening}\n")
    messages.append({"role": "user", "content": seed})
    messages.append({"role": "assistant", "content": opening})

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled. No policy was saved.")
            return 1

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Exiting. No policy was saved.")
            return 1

        # 'generate' command forces immediate policy generation.
        force_generate = user_input.lower() in ("generate", "gen", "create")
        if force_generate:
            content = (
                "I have provided enough information. "
                "Please generate the complete policy YAML now in a ```yaml block."
            )
        else:
            content = user_input
            user_turn_count += 1

        # After max turns, append a generate instruction to the user's message.
        if not force_generate and user_turn_count >= _MAX_TURNS_BEFORE_GENERATE:
            content = (
                f"{user_input}\n\n"
                "You now have enough information. "
                "Generate the complete policy YAML immediately in a ```yaml block."
            )

        messages.append({"role": "user", "content": content})
        response = chat_turn(messages, provider)
        messages.append({"role": "assistant", "content": response})

        # Check for a YAML block in the response.
        yaml_block = extract_yaml_block(response)
        if yaml_block:
            is_valid, error, _ = validate_policy_yaml(yaml_block)
            if is_valid:
                last_valid_yaml = yaml_block
                # Strip the yaml block from the printed response to avoid duplication,
                # then show the policy and ask to save.
                prose = response.replace(f"```yaml\n{yaml_block}\n```", "").strip()
                if prose:
                    print(f"\nAssistant: {prose}\n")
                if _prompt_save(last_valid_yaml, output):
                    return 0
                # User wants adjustments — treat their answer as next input.
                try:
                    adjustment = input("You: ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nCancelled.")
                    return 1
                if adjustment:
                    messages.append({"role": "user", "content": adjustment})
                    response2 = chat_turn(messages, provider)
                    messages.append({"role": "assistant", "content": response2})
                    yaml_block2 = extract_yaml_block(response2)
                    if yaml_block2:
                        is_valid2, _, _ = validate_policy_yaml(yaml_block2)
                        if is_valid2:
                            last_valid_yaml = yaml_block2
                    print(f"\nAssistant: {response2}\n")
            else:
                print(f"\nAssistant: {response}")
                print(f"\n[Validation issue: {error} — ask me to fix it.]\n")
        else:
            print(f"\nAssistant: {response}\n")


def main(args: list | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ghascompliance generate-policy",
        description="Generate a GitHub security policy YAML using AI.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--description", "-d",
        metavar="TEXT",
        help="Natural language description of the desired policy (single-shot mode).",
    )
    mode_group.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start an interactive conversation to build the policy step by step.",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Save the generated policy to this file (default: print to stdout).",
    )
    parser.add_argument(
        "--provider", "-p",
        default=None,
        choices=SUPPORTED_PROVIDERS,
        metavar="PROVIDER",
        help=(
            f"AI provider to use: {', '.join(SUPPORTED_PROVIDERS)} "
            "(default: gemini). Can also be set via AI_PROVIDER env var."
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="MODEL",
        help="Override the default model for the chosen provider.",
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
        sys.exit(
            run_interactive(
                output=parsed.output,
                provider_name=parsed.provider,
                model=parsed.model,
            )
        )
    elif parsed.description:
        sys.exit(
            run_single_shot(
                description=parsed.description,
                output=parsed.output,
                provider_name=parsed.provider,
                model=parsed.model,
                max_retries=parsed.max_retries,
            )
        )
    else:
        parser.print_help()
        sys.exit(0)
