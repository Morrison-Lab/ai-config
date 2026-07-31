# Launcher wiring for the shiva dotfiles. Source this from ~/.zshrc:
#
#     source ~/Projects/ai-config/dotfiles/shiva/zshrc-fragment.zsh
#
# ~/.zshrc itself is not tracked -- it carries personal credential helpers
# (gh-unlock/gh-lock and the GPG token path) that don't belong in a repo. Only
# these two pieces are load-bearing for the launchers, so only these are
# tracked: without the PATH line the launchers aren't callable at all, and
# without the hook they lose per-project conda-env selection.

# Add ~/bin to PATH (tui-alloc / claude-alloc / codex-alloc launchers)
export PATH="$HOME/bin:$PATH"

# Auto-select conda env for the tui-alloc / claude-alloc / codex-alloc launchers,
# scoped by directory (poor-man's direnv; keeps the launchers project-agnostic).
_tui_alloc_env() {
  case "$PWD" in
    "$HOME/Projects/bcs"*) export ALLOC_CONDA_ENV=bcs ;;
    *) unset ALLOC_CONDA_ENV ;;
  esac
}
autoload -Uz add-zsh-hook
add-zsh-hook chpwd _tui_alloc_env
_tui_alloc_env
