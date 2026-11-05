# Avoid unintentional plagiarism

A language model that has read a textbook can reproduce its sentences from memory without knowing it, and a bulk-generated chapter ("content from multiple sources") can carry passages that no author ever reviewed for provenance.
Credit alone ([`visible-attributions.md`](visible-attributions.md)) does not cure a copied passage: the text must be the author's own, or be a marked quotation.

## Writing rules

- Write each explanation from the mathematics, the data, or the code in front of you, in your own sentence structure.
- Never reword a source sentence by sentence.
  Swapping synonyms into someone else's sentence is still copying.
- A passage adapted from a source carries a citation with a locator at the passage, and a Source note when it follows the source's structure for more than a sentence ([`citations.md`](citations.md)).
- Quote only with quotation marks or a blockquote and a citation, and keep quotes short ([quote the original](citations.md)).
- A passage you cannot derive yourself and cannot trace to a source is a warning sign.
  Find the source, cite it, and rewrite from it, or cut the passage.

## Check before pushing

Run the overlap checker over what you wrote:

```bash
python3 check_source_overlap.py --corpus <dir of extracted .txt> --git-diff origin/main
```

- The tool is `check-source-overlap` in [`Morrison-Lab/gha`](https://github.com/Morrison-Lab/gha) (a composite action, a reusable workflow, and the standalone script `check-source-overlap/check_source_overlap.py`, which a notes repository may also carry as `tools/check_source_overlap.py`).
- `--git-diff` checks only the lines a branch adds.
  To check content already on `main`, name the files instead: `python3 check_source_overlap.py --corpus <dir> chapters/*.qmd`.
- The corpus is text extracted with `pdftotext` from the books in `Morrison-Lab/mlr`, kept in a scratch directory and never committed.
- Web sources (a free online book, a documentation page) go into the corpus as `.txt` files too.
- Fix every flagged paragraph by rewriting it from scratch, or quote and cite it.
  Mark a hand-checked generic definition or standard formula with `<!-- overlap-ok: reason -->`.
- Read the `examined` count in the summary line.
  Zero is legitimate only when the input holds no unquoted prose: a `--git-diff` change that adds none, or a page that is wholly quoted.
  Confirm that, and treat any other zero as a run that checked nothing.

## Existing content

Treat bulk-generated commits as the highest risk.
Find them from commit messages such as "content from multiple sources", from bot authors, and from commits that add whole chapters at once, then run the checker over those files first.
A flagged paragraph is rewritten from scratch, or turned into a short marked quotation with a citation, in its own PR.
A citation alone never clears a paragraph that copies the source's wording.
Never fix a flagged paragraph silently: the PR description names the paragraph, the source it overlapped, and the commit that introduced it, so the maintainer can see what was found and how far the problem reaches.

## Limits

The checker finds copying that a corpus holds.
It cannot find a source nobody put in the corpus, and it misses a paraphrase that keeps no run of six consecutive words.
It is a net, not a proof of originality.
