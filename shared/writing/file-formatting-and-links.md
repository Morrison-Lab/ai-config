# File formatting and links

Formatting defaults for responses and documentation: GitHub-style markdown, liberal hyperlinks, links or backticks for files and symbols, linked PRs and issues, and semantic line breaks.

- Use GitHub-style markdown for all responses and documentation.
- Hyperlink liberally to make it easy for readers to find more information;
  see [`hyperlink-liberally`](hyperlink-liberally.md).
- When referencing files or symbols, use relative markdown links or inline code backticks.
- When mentioning PRs or issues, format them as clickable hyperlinks to forge URLs, never bare `#NNN` (except `Closes #123`).
- Semantic line breaks everywhere, enforced by CI ([rule](semantic-line-breaks.md)).

- **Don't:** link a `#NNN` a passage is displaying rather than citing, or leave referenced tools, forge items or policies unlinked.

These rules moved verbatim from `AGENTS.md`'s "File formatting & links" section ([ai-config#5310](https://github.com/Morrison-Lab/ai-config/issues/5310)), which keeps its absolute rules inline and points here for the rest.
