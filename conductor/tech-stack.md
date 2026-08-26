# Technology Stack: `ai-config`

## Core Languages & Runtimes
- **Python 3.10+** (as of Aug 2026): Core implementation language for repository validation, skill wrapper generation, link checking, hook implementations, and standalone test suites.
- **Bash / POSIX Shell**: Portability layer for `bootstrap.sh`, harness setup scripts, and environment lifecycle management.
- **Markdown & Quarto**: Authoring formats for human/agent documentation, skill manuals, shared fragments, and website compilation (`_quarto.yml`).

## Quality Assurance & Verification
- **Testing**: Native Python test suites (`scripts/test_*.py`, `hooks/test-*.py`) executed directly via `python3` or `pytest`.
- **Formatting & Linting**: `markdownlint-cli2` (configured via `.markdownlint-cli2.jsonc`) and custom validation scripts (`scripts/validate-skills.py`, `scripts/check-links.py`, `scripts/check-context-closure.py`).
- **Hook Management**: Git pre-commit framework (`.pre-commit-config.yaml`) and runtime agent enforcement hooks (`hooks/`).

## Infrastructure & Configuration Formats
- **CI/CD**: GitHub Actions workflows (`.github/workflows/validate.yml`, sync workflows, gha integrations).
- **Configuration & Manifests**: YAML (`tool-mappings.yml`), JSON (`opencode.json`, `.agents/skills.json`, `.agents/plugins.json`, `hooks/hooks.json`).
- **Target Agent Harnesses**: Anthropic Claude Code, Google Antigravity / Gemini CLI, OpenAI Codex CLI, Cursor, OpenCode, VS Code Copilot.
