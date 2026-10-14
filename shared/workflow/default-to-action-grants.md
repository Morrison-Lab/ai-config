# Default to action without asking: installs and `add_repo`

Detail for [`AGENTS.md`'s "Default to action without asking"](../../AGENTS.md), moved here, word for word, to keep `AGENTS.md` under Codex's byte cap.

The grant covers installing and updating software: R, R packages (including through `renv`), Quarto, and any other tool, on any machine where the owner has install access, directly or through conda, mamba, pyenv, Homebrew, or a similar manager.
Do it whenever it helps, without asking (owner directive, 2026-10-02).
A resulting lockfile change (`renv.lock`, `environment.yml`) is a repo change and goes through the normal PR flow.

It covers attaching any repository (`add_repo`) whenever that helps, even only to read it.
Posting there still passes the membership gate in `AGENTS.md`;
where it does, file or fix without offering first.

- **Do:** attach a repository as soon as it would help.
- **Don't:** ask first, or write "would need `add_repo`" and wait (ai-config#4337).
