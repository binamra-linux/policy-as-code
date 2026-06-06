"""Streamlit web UI for the AI-Assisted Policy as Code tool."""

import os
import sys
import subprocess
import tempfile

import streamlit as st

# Ensure the project root is on the path so ghascompliance imports work.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="AI Policy as Code",
    page_icon="🔒",
    layout="wide",
)

st.title("🔒 AI-Assisted Policy as Code")
st.caption("Generate security policies with AI · Run compliance checks · Get plain-English explanations")

tab_generate, tab_check = st.tabs(["📝 Generate Policy", "🔍 Compliance Check"])


# ── Tab 1: Policy Generator ───────────────────────────────────────────────────
with tab_generate:
    st.header("AI Policy Generator")
    st.write("Describe your security requirements in plain English and get a valid policy YAML.")

    col1, col2 = st.columns([2, 1])

    with col1:
        description = st.text_area(
            "Policy description",
            placeholder=(
                "Example: Block critical and high severity CVEs. "
                "Give teams 14 days to fix high severity issues. "
                "Reject GPL licenses. Flag all secrets."
            ),
            height=120,
        )

    with col2:
        provider = st.selectbox("AI Provider", ["groq", "gemini", "anthropic"], index=0)
        output_file = st.text_input("Save to file (optional)", placeholder="policy.yml")

    if st.button("Generate Policy", type="primary", disabled=not description.strip()):
        with st.spinner("Generating policy..."):
            try:
                from ghascompliance.ai.generator import generate_single_shot
                from ghascompliance.ai.validator import validate_policy_yaml
                from ghascompliance.ai.providers.factory import get_provider

                prov = get_provider(provider)
                yaml_str = generate_single_shot(description, prov)
                is_valid, error, _ = validate_policy_yaml(yaml_str)

                if is_valid:
                    st.success("Policy generated and validated successfully.")
                    st.code(yaml_str, language="yaml")

                    if output_file.strip():
                        with open(output_file.strip(), "w") as fh:
                            fh.write(yaml_str)
                        st.info(f"Saved to `{output_file.strip()}`")

                    st.download_button(
                        label="Download policy.yml",
                        data=yaml_str,
                        file_name=output_file.strip() or "policy.yml",
                        mime="text/yaml",
                    )
                else:
                    st.error(f"Validation failed: {error}")
                    st.code(yaml_str, language="yaml")

            except EnvironmentError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Error: {exc}")


# ── Tab 2: Compliance Checker ─────────────────────────────────────────────────
with tab_check:
    st.header("Compliance Checker")
    st.write("Run a compliance check against a GitHub repository using your policy.")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        github_token = st.text_input(
            "GitHub Token",
            type="password",
            value=os.environ.get("GITHUB_TOKEN", ""),
            help="Personal access token with repo and security_events scopes.",
        )
        repository = st.text_input(
            "Repository",
            placeholder="owner/repo",
            help="The GitHub repository to check.",
        )

    with col_right:
        policy_source = st.radio("Policy source", ["Upload file", "Paste YAML"])
        if policy_source == "Upload file":
            uploaded = st.file_uploader("Policy YAML file", type=["yml", "yaml"])
            policy_yaml = uploaded.read().decode() if uploaded else ""
        else:
            policy_yaml = st.text_area("Policy YAML", height=180, placeholder="general:\n  level: error\n...")

        explain = st.checkbox("Generate AI explanation", value=True)
        explain_provider = st.selectbox("Explanation provider", ["groq", "gemini", "anthropic"], key="ep")

    disable_checks = st.expander("Disable checks (optional)")
    with disable_checks:
        c1, c2, c3 = st.columns(3)
        dis_code = c1.checkbox("Code Scanning")
        dis_dep = c2.checkbox("Dependabot")
        dis_sec = c3.checkbox("Secret Scanning")

    can_run = bool(github_token and repository and policy_yaml.strip())

    if st.button("Run Compliance Check", type="primary", disabled=not can_run):
        # Write policy to a temp file so the CLI can read it.
        with tempfile.NamedTemporaryFile(suffix=".yml", mode="w", delete=False) as tmp:
            tmp.write(policy_yaml)
            tmp_path = tmp.name

        cmd = [
            sys.executable, "-m", "ghascompliance",
            "--github-token", github_token,
            "--github-repository", repository,
            "--github-policy-path", tmp_path,
            "--severity", "error",
            "--display",
            "--action", "continue",
        ]
        if dis_code:
            cmd.append("--disable-code-scanning")
        if dis_dep:
            cmd.append("--disable-dependabot")
        if dis_sec:
            cmd.append("--disable-secret-scanning")

        env = os.environ.copy()
        env["GITHUB_TOKEN"] = github_token

        with st.spinner("Running compliance check..."):
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )

        os.unlink(tmp_path)

        # Parse output into violations and summary
        stdout_lines = result.stdout.splitlines() + result.stderr.splitlines()
        violations = [l for l in stdout_lines if "Alert ::" in l or "Violation ::" in l]
        total_line = next((l for l in stdout_lines if "Total unacceptable alerts" in l), "")
        total_errors = 0
        if total_line:
            try:
                total_errors = int(total_line.strip().split("::")[-1].strip())
            except ValueError:
                pass

        # Results
        if total_errors == 0:
            st.success(f"✅ PASSED — No policy violations found in `{repository}`")
        else:
            st.error(f"❌ FAILED — {total_errors} violation(s) found in `{repository}`")

        if violations:
            st.subheader("Violations")
            sev_order = {"critical": 0, "high": 1, "error": 2, "medium": 3, "low": 4}
            rows = []
            for v in violations:
                parts = v.split("::")
                if len(parts) >= 2:
                    detail = parts[-1].strip()
                    sev = "unknown"
                    for s in sev_order:
                        if f"({s})" in v.lower():
                            sev = s
                            break
                    rows.append({"Severity": sev.upper(), "Detail": detail})

            rows.sort(key=lambda r: sev_order.get(r["Severity"].lower(), 99))

            import pandas as pd
            df = pd.DataFrame(rows)

            def highlight(row):
                color = {"CRITICAL": "#ffcccc", "HIGH": "#ffe0cc", "ERROR": "#fff0cc"}.get(row["Severity"], "")
                return [f"background-color: {color}"] * len(row)

            st.dataframe(df.style.apply(highlight, axis=1), use_container_width=True)

        with st.expander("Raw output", expanded=False):
            st.code(result.stdout + result.stderr, language="text")

        if explain and (violations or total_errors > 0):
            st.subheader("AI Explanation")
            with st.spinner("Generating AI explanation..."):
                try:
                    from ghascompliance.ai.explainer import explain_results
                    report = explain_results(
                        repository=repository,
                        violations=[v for v in stdout_lines if "Alert ::" in v],
                        total_errors=total_errors,
                        provider_name=explain_provider,
                    )
                    st.markdown(report)
                except Exception as exc:
                    st.error(f"AI explainer error: {exc}")
