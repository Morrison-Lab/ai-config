[hook: no-macro-claim-without-definition] This message says what a LaTeX macro prints or means
({macros}: "{sentence}"),
and no Read, Grep or Bash result in this session shows the macro's definition.
On 2026-11-24 an agent told Ezra that `\vx` "prints a bold x"
(it prints x with an underset tilde)
and that swapping `\Sigma` for `\covmat` would change a chapter's notation
(`\covmat` is defined as `\Sigma`).
Both claims came from recall, and the definitions sit in macros.qmd.

Read the macro's definition in macros.qmd
(the latex-macros submodule, or the repo's own macros.qmd)
before saying what it prints,
then state what the definition says.
A backtick around the name does not make the claim safe.
If the definition cannot be read from this session,
say the rendering is unverified and drop the claim.
ai-config#6109.
