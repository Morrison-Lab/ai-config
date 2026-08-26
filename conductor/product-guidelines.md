# Product Guidelines: `ai-config`

## Voice & Tone
- **Direct & Technical**: Clear, active voice without fluff, hype, or conversational filler.
- **Empirical & Vintage-Aware**: All claims about third-party tools, CLIs, harnesses, or APIs must be dated/version-bounded (`shared/writing/timestamp-volatile-claims.md`).
- **No AI Tells**: Avoid empty transitions and recognizable synthetic prose artifacts (`shared/writing/ai-tells.md`).

## Formatting & Writing Conventions
- **Semantic Line Breaks (SemBr)**: Break markdown lines at semantic sentence boundaries and natural clause boundaries for readable diffs.
- **GitHub Flavored Markdown**: Standard syntax, clean tables, and explicit relative file/symbol links (`[filename](path/to/file)`).
- **ASCII-Safe Shared Fragments**: Shared instruction fragments under `shared/` must remain pure ASCII (use `---` for em-dashes and straight quotes) to maintain cross-compatibility with Quarto and upstream documentation submodules.

## Multi-Agent Interaction Principles
- **Explicit Attribution**: Every forge comment posted by an automated agent must include the standardized disclosure line (`_Posted by <Agent Name> (AI agent) --- not written by a human._`).
- **Action Over Empty Promises**: Never promise future behavior in prose without shipping a concrete, automated mechanism (rule, hook, or issue).
- **Adversarial Verification**: Deliverables must be verified through separate subagent review before publishing.
