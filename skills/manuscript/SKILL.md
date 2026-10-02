---
name: manuscript
description: "Prepare a paper for a journal."
user-invocable: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
---

# manuscript --- get a scientific paper ready to submit

Apply standard journal conventions to a research manuscript without being asked, then verify the rendered output page by page.
Use this skill whenever drafting, revising, rendering, or reviewing a paper or its supplement meant for a peer-reviewed journal.

**Precedence.**
The target journal's *Instructions for Authors* override everything here (word limits, abstract headings, reference style, where figures go, file formats).
Read them first when a journal is named.
When none is named, use the defaults below, which follow the [ICMJE Recommendations](https://www.icmje.org/recommendations/) and [AMA Manual of Style](https://www.amamanualofstyle.com/) conventions common in clinical and health-services journals.
The reader-facing version of this guide is PSW's chapter "Preparing a manuscript for submission" (added by [psw#74](https://github.com/Morrison-Lab/psw/pull/74));
when the two disagree, defer to PSW and fix this skill to match.
For prose style, defer to [PSW](https://morrison-lab.github.io/psw/) and the [`use-preferred-style`](../use-preferred-style/SKILL.md) skill.

## 1. Document order

Assemble the main document in this order:

1. **Title page** (section 2).
2. **Structured abstract** (section 3), then keywords and, if the journal uses them, Key Points.
3. **Main text** in IMRaD order: Introduction, Methods, Results, Discussion (with a Limitations subsection or paragraph), Conclusions.
4. **Back matter**: Acknowledgments, author contributions, funding, conflict of interest disclosures, data and code availability, ethics statement (when the journal wants these in the text rather than in a form).
5. **References.**
6. **Tables**, each starting on its own page, numbered in citation order.
7. **Figures**, each on its own page with its caption on the same page.
8. **Page break**, then the **Supplement** (section 9), as a separate file if the journal requires one.

Tables and figures go at the end of the main text, not inline.
Many journals also want figures uploaded as separate files with legends listed after the references;
when that is the instruction, follow it and keep the end-of-document copies only for review drafts.

## 2. Title page

- **Title**: specific and informative, naming the population, exposure or intervention, outcome, and design where they fit (for example, "... : A Difference-in-Differences Analysis").
  No abbreviations, no question titles, no puns.
  Check the character limit.
- **Running head** (short title) if required.
- **Authors**: full names, highest degrees if the journal wants them, affiliations, ORCID iDs.
  Byline order is agreed among the authors, not inferred.
- **Corresponding author**: name, postal address, email.
- **Word counts**: abstract and main text (Introduction through Discussion;
  excludes abstract, references, tables, figure legends).
- Counts of tables, figures, and references.
- Trial or protocol registration number, when applicable.

**Authorship** follows the four [ICMJE criteria](https://www.icmje.org/recommendations/browse/roles-and-responsibilities/defining-the-role-of-authors-and-contributors.html): substantial contribution to conception, design, data acquisition, or analysis;
drafting or critical revision;
final approval;
and accountability.
Everyone else goes in Acknowledgments, with permission.
Describe contributions with the [CRediT taxonomy](https://credit.niso.org/) when the journal asks.

## 3. Abstract

- **Structured**, using the journal's headings.
  A generic default: Background (or Importance), Objective, Methods (Design, Setting, and Participants;
  Exposure;
  Main Outcomes and Measures), Results, Conclusions (and Relevance).
- Typically 250 to 350 words.
  Check the limit.
- Results give the sample size and the main effect estimates with 95% CIs, not only P values.
  Report the primary outcome first.
- Conclusions follow from the results and match the design: no causal language from an observational design unless the identification strategy supports it, and say what that strategy is.
- No citations, no undefined abbreviations, no figure or table references.
- Keywords: 3 to 6, preferably [MeSH](https://meshb.nlm.nih.gov/) terms.

## 4. Main text by section

### Introduction

Three short paragraphs is usually enough: what is known, the gap, and the objective or hypothesis.
End with a sentence stating the aim.
Do not preview results.

### Methods

Enough detail that another analyst could reproduce the analysis.

- Study design and setting (place, dates of each period).
- Data sources and how records were linked.
- Participants: eligibility, exclusions with counts, and a flow diagram when exclusions are non-trivial.
- Exposure or intervention definition, including timing.
- Outcomes: primary and secondary, with units and how each was measured.
- Covariates and why they were included.
- Statistical analysis: the estimand, the model, assumptions and how they were checked, handling of missing data, clustering or correlation, multiple comparisons, sensitivity analyses, software with versions.
  Cite the methods papers.
- Ethics: IRB approval or exemption with protocol number, consent or waiver.
- The reporting guideline followed (section 5).

### Results

- Open with the analytic sample and its characteristics (Table 1).
- Report the primary outcome, then secondary outcomes, then sensitivity analyses, in the order the Methods introduced them.
- Report numbers; do not interpret them here.
  Do not restate every table cell in the text;
  give the key estimates and point to the table.
- Cite every table and figure in the text, in numerical order, at first relevant mention.

### Discussion

1. Principal findings in one paragraph, without repeating the numbers.
2. Comparison with prior work, with citations.
3. Interpretation and possible mechanisms, labelled as such.
4. **Limitations**: honest and specific (confounding, selection, measurement, generalizability, power), each with its likely direction and what was done about it.
5. Implications for practice, policy, or research.

### Conclusions

Two to four sentences that the data support.
No new results.

## 5. Reporting guidelines

Pick the guideline for the design from the [EQUATOR Network](https://www.equator-network.org/), follow it while writing, and submit the completed checklist if the journal asks.
Common ones:

| Design | Guideline |
|---|---|
| Observational (cohort, case-control, cross-sectional) | STROBE |
| Observational using routinely collected or EHR data | RECORD (extends STROBE) |
| Randomized trial | CONSORT |
| Trial protocol | SPIRIT |
| Systematic review or meta-analysis | PRISMA |
| Diagnostic accuracy | STARD |
| Prediction model (including machine learning) | TRIPOD (TRIPOD+AI) |
| Quality improvement | SQUIRE |
| Economic evaluation | CHEERS |
| Qualitative research | SRQR or COREQ |
| Animal research | ARRIVE |
| Statistical reporting in general | SAMPL |

Check the EQUATOR page for the current version before citing one.

## 6. Tables

- **Numbered** in citation order (Table 1, Table 2, ...) and **captioned**.
  Every table has both.
- The caption (title) goes **above** the table and says what, who, where, and when, in a phrase: "Table 2.
  Change in Work RVUs per Clinic Session After AI Scribe Adoption, 2023--2025".
- Self-contained: a reader should understand it without the text.
- Column headers carry units; use the same units and decimals down a column.
- Horizontal rules only (top, below header, bottom).
  No vertical rules, no shading, no color unless the journal allows it.
- Footnotes below the table: define every abbreviation used in the table, even if defined in the text;
  explain symbols and notes with superscript letters (a, b, c) in order of appearance;
  state the statistical test or model behind each P value or estimate.
- Give denominators: "45 (12.3%)", or put N in the column header.
- Table 1 describes the sample by group, without P values for baseline comparisons in a trial;
  standardized mean differences are better for observational comparisons.
- A table must fit the page width.
  Split a wide table or move it to the supplement;
  never let it run off the margin.
- Caption placement and page breaks around tables follow the `manuscript-float-layout` fragment ([ai-config#4203](https://github.com/Morrison-Lab/ai-config/pull/4203)).

## 7. Figures

- **Numbered** in citation order and **captioned**.
  The legend goes **below** the figure: a title phrase, then sentences explaining panels, symbols, error bars ("Error bars indicate 95% CIs"), and abbreviations.
- Axis labels with units; consistent fonts across figures.
- **Size each figure for the page.**
  The plotted content fills the available width (the text width, or the journal's stated figure width), with no large blank margins or empty space inside the image.
  Every piece of text in it (axis labels, tick labels, node and legend labels) is at least the journal's stated minimum, and in any case about 8 pt or larger at the printed size.
  Set the figure's width and height (`fig-width`/`fig-height`, or the export size) to that width and an aspect ratio that fits the content, rather than exporting at a default size and letting the document scale it down.
  Wide diagrams such as Sankey plots often fail this rule: the plot ends up tiny in a field of white space.
  For a ggplot, preview it at those exact dimensions before rendering with [ggview](https://github.com/idmn/ggview): add `canvas(6.5, 4)` (the final width and height, in inches by default) to the plot.
  The preview opens in the RStudio IDE's viewer (through `rstudioapi::viewer()`);
  in any other editor, save the plot with `ggview::save_ggplot()` and open the saved file instead.
  In a Quarto chunk, copy those dimensions into `fig-width`/`fig-height`;
  for a figure saved to a file, save it with `ggview::save_ggplot()`, which uses the canvas size.
  Remove `canvas()` from any plot that a chunk prints into the document: printing a plot that carries it calls `rstudioapi::viewer()` instead of drawing it, so the figure never reaches the document, and a render outside the RStudio IDE (from a terminal or CI) stops with "RStudio not running".
  A plot saved with `save_ggplot()` can keep its `canvas()`, since that is where the saved size comes from.
  Judge it on the rendered page.
  The printed size of the plot's text is its font size in the plot code times the displayed width divided by `fig-width`;
  as a quick visual check, figure text far smaller than the caption beneath it is almost certainly below 8 pt.
- Colorblind-safe palettes, and do not use color as the only way to tell groups apart;
  pair it with shape or line type.
- Show the data where possible (points with intervals beat bar charts of means).
  Start a bar axis at zero.
- Vector formats (PDF, EPS, SVG) for plots;
  raster at 300 dpi or more (600 to 1200 for line art) in TIFF or PNG.
- Multi-panel figures label panels A, B, C and refer to them in the legend.
- Add alt text when the journal or venue supports it (see [`alt-text`](../alt-text/SKILL.md)).
- Caption placement and page breaks around figures follow the `manuscript-float-layout` fragment ([ai-config#4203](https://github.com/Morrison-Lab/ai-config/pull/4203)).

## 8. Statistics and numbers

- **Estimates with uncertainty**: give the point estimate with its 95% CI.
  Format consistently, for example "0.82 (95% CI, 0.71 to 0.95)" or "0.82 (95% CI, 0.71--0.95)".
  Use "to" when a bound is negative.
- **P values**: exact values to 2 or 3 decimals ("P = .03", "P = .21");
  "P < .001" below that.
  AMA style uses no leading zero and a capital italic *P*.
  Never "P = 0.000" or "NS".
- Prefer estimates and intervals over significance language.
  Do not write "trend toward significance" or "marginally significant".
  Reserve "significant" for its statistical meaning, and avoid it for importance.
- A wide interval means the estimate **had more uncertainty**;
  write that, not "less precise" or "imprecise".
  Absence of evidence is not evidence of absence: an interval that crosses the null is compatible with both benefit and harm, so say so.
- **Descriptive statistics**: mean (SD) for roughly symmetric data, median (IQR) for skewed data;
  counts with percentages.
- **Decimals**: no more precision than the data support.
  Percentages to one decimal (or whole numbers when n < 100);
  ratios to two decimals;
  keep the same precision for the same quantity everywhere.
- Spell out numbers that begin a sentence, or rewrite the sentence.
  Use digits for measurements and statistics.
- Units: SI or the journal's convention, with a space between number and unit ("5 mg");
  thousands separators per the journal ("12,345").
- Name the estimand and model for every effect: "average treatment effect on the treated, estimated with the Callaway and Sant'Anna difference-in-differences estimator".
- Numbers in the text, tables, figures, and abstract must agree.
  Generate them from code (inline R in Quarto), never by retyping.

## 9. Supplement

- A separate document (or a clearly separated part after a page break) with its own title, the paper's title and authors, and a table of contents.
- Number items with the journal's scheme: "eTable 1", "eFigure 1", "eMethods" (JAMA style) or "Table S1", "Figure S1".
  Same numbering and caption rules as the main text.
- Cite each supplement item from the main text, in order.
- The supplement is where these belong: extended methods, full model output, sensitivity analyses, additional tables, code and software versions, data-processing details, and any pipeline or audit notes (data-quality checks, exclusions traced step by step, reconciliation with earlier reports).
- Keep it as polished as the main text: same caption, table, and abbreviation rules.

## 10. Abbreviations

- Define each abbreviation at first use in the abstract and again at first use in the main text, then use it consistently.
- Define abbreviations again in each table and figure footnote or legend.
- Abbreviate only terms used several times.
  Do not abbreviate in the title.
- Standard units and very common terms (CI, SD, IQR, US) need no definition in most journals;
  check the journal's list.

## 11. References

- Use the journal's style (AMA/Vancouver numbered by default).
  Generate the list from a `.bib` file with a CSL style; never format by hand.
- Number in order of first citation;
  a citation in a table or figure counts at the point where that table or figure is first cited.
- Cite the primary source, and check every reference exists and supports the sentence it is attached to (see [`purge-hallucinations`](../purge-hallucinations/SKILL.md) and [`shared/writing/citations.md`](../../shared/writing/citations.md)).
- Include DOIs when the style allows.
  Check for retractions.
- Cite software and R packages you relied on.

## 12. Prose

- Follow [`use-preferred-style`](../use-preferred-style/SKILL.md): plain, direct, short sentences, active voice.
- Past tense for what was done and found (Methods, Results);
  present tense for established knowledge and for what the findings mean.
- Match causal language to the design.
  "Was associated with" for associations;
  causal verbs only when the design and assumptions earn them, and state the assumptions.
- No clichés or AI tells: no "novel", "groundbreaking", "delve", "crucial", "landscape", "underscore", "it is worth noting", and no "not just X but Y" antitheses.
  Run [`find-ai-tells`](../find-ai-tells/SKILL.md).
- **No pipeline, audit, or process notes in the main text.**
  No mentions of scripts, file names, variable names, merge requests, code versions, reviewer conversations, "as noted in the earlier draft", TODOs, or changelog-style asides.
  Those go in the supplement or nowhere.
- One term per concept throughout; do not vary terms for elegance.
- Define every group, period, and outcome before using it.
- Run [`fact-check-prose`](../fact-check-prose/SKILL.md) on claims and numbers against the rendered output.

## 13. Required statements

Most journals require each of these, in the text or in submission forms:

- Funding sources and the funder's role.
- Conflict of interest disclosures ([ICMJE disclosure form](https://www.icmje.org/disclosure-of-interest/)).
- Ethics approval and consent.
- Data availability and code availability.
- Trial or protocol registration.
- Use of AI tools in writing or analysis, if the journal's policy asks.
- Prior presentation or preprint.

## 14. Rendering and layout (Quarto)

- Render from source every time; do not edit the output file.
- Float placement, page breaks, and caption rules (floats after the references, a break before the supplement, captions on their float's page and rendered as captions rather than headings) live in the `manuscript-float-layout` fragment ([ai-config#4203](https://github.com/Morrison-Lab/ai-config/pull/4203));
  follow it rather than restating it here.
- Table captions on top (`tbl-cap-location: top`), figure captions below (`fig-cap-location: bottom`).
  Use div syntax for labels and captions ([`quarto-figure-captions.md`](../../shared/writing/quarto-figure-captions.md)).
- Double spacing, line numbers, and page numbers if the journal asks (common for review copies).
- Cross-references must resolve; run [`check-rendered-refs`](../check-rendered-refs/SKILL.md).

## 15. Pre-submission checklist

A green build is not "done".
Item 1 is a hard gate: no manuscript PR or MR is reported ready or merged, under any grant, until it passes ([`review-rendered-documents`](../../shared/workflow/review-rendered-documents.md)).
Before calling a manuscript ready:

1. [ ] Export the render to PDF and **look at every page**, main text and supplement.
2. [ ] Every table and figure has a number and a caption, and is cited in the text in order.
3. [ ] The rendered layout passes every rule in the `manuscript-float-layout` fragment ([ai-config#4203](https://github.com/Morrison-Lab/ai-config/pull/4203)).
4. [ ] No table runs off the page;
   no figure is cropped or blurry;
   every figure fills the available width without large blank margins, and its smallest text is about 8 pt or larger (section 7).
5. [ ] No broken cross-references (`??`, `@fig-`, `Table ?`), raw Markdown, code output, warnings, or `NA` in rendered tables.
6. [ ] Abstract numbers match the Results, tables, and figures.
7. [ ] Every abbreviation is defined at first use (abstract, text, each table and figure).
8. [ ] Estimates carry 95% CIs; P values and decimals follow section 8.
9. [ ] No pipeline or audit notes, file names, or TODOs in the main text.
10. [ ] Reporting-guideline checklist completed, with page numbers.
11. [ ] References resolve, are in order, and support their sentences.
12. [ ] Title page complete: authors, affiliations, corresponding author, word counts.
13. [ ] Required statements present (section 13).
14. [ ] Word, table, figure, and reference counts within the journal's limits.
15. [ ] AI-tell and fact-check passes done.
16. [ ] Cover letter drafted: the question, the main finding, why this journal, confirmation that the work is not under consideration elsewhere, and any suggested or excluded reviewers.

Report the manuscript as ready only after this checklist passes, and say which items were checked on the rendered PDF.
Post the page-by-page evidence on the PR or MR as that fragment describes.
