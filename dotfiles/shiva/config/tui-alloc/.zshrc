# Loaded only inside `tui-alloc` allocations, via ZDOTDIR.
# Bring in your normal shell (PATH, conda hook, aliases), then set up the
# session and launch the agent. When the agent exits you drop to an
# interactive prompt still inside the allocation and the bcs env.
[[ -f "$HOME/.zshrc" ]] && source "$HOME/.zshrc"

# Activate a conda env only if one was requested (ALLOC_CONDA_ENV). These
# launchers are global — no project env is assumed by default.
[[ -n "$ALLOC_CONDA_ENV" ]] && conda activate "$ALLOC_CONDA_ENV"

[[ -n "$TUI_ALLOC_PWD" ]] && cd "$TUI_ALLOC_PWD"
"${TUI_ALLOC_CMD:-claude}"
