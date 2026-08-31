#!/usr/bin/env python3
"""Tests for scripts/check_doi_bib.py.

Verifies deterministic DOI-vs-.bib metadata checking, BibTeX parsing, LaTeX
cleaning, fuzzy matching, and fabrication detection.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_doi_bib as cdb

passes = 0
failures = 0


def check(name: str, condition: bool, msg: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {msg}".rstrip())
        failures += 1


def test_clean_latex() -> None:
    # Accents
    check("clean_latex: umlaut", cdb.clean_latex(r'M\"uller') == "Müller")
    check("clean_latex: acute", cdb.clean_latex(r"Poincar\'e") == "Poincaré")
    check("clean_latex: cedilla", cdb.clean_latex(r"\c{c}a") == "ça")
    check("clean_latex: tilde", cdb.clean_latex(r"Se\~nor") == "Señor")
    check("clean_latex: german sz", cdb.clean_latex(r"Stra\ss e") == "Straße")
    check("clean_latex: ring a", cdb.clean_latex(r"\aa ngstr\o m") == "ångstrøm")

    # Command wrappers & braces
    check(
        "clean_latex: textbf & emph",
        cdb.clean_latex(r"\textbf{Important} \emph{Results}") == "Important Results",
    )
    check(
        "clean_latex: enquote & braces",
        cdb.clean_latex(r"\enquote{{Machine} {Learning}}") == "Machine Learning",
    )
    check(
        "clean_latex: html tags",
        cdb.clean_latex("<i>Title</i> <jats:p>Text</jats:p>") == "Title Text",
    )


def test_normalize_doi() -> None:
    check("normalize_doi: plain", cdb.normalize_doi("10.1000/182") == "10.1000/182")
    check(
        "normalize_doi: https url",
        cdb.normalize_doi("https://doi.org/10.1000/182") == "10.1000/182",
    )
    check(
        "normalize_doi: dx url",
        cdb.normalize_doi("http://dx.doi.org/10.1000/182/") == "10.1000/182",
    )
    check(
        "normalize_doi: doi prefix",
        cdb.normalize_doi("doi: 10.1000/182") == "10.1000/182",
    )
    check("normalize_doi: empty", cdb.normalize_doi("") == "")


def test_extract_first_author_surname() -> None:
    check(
        "author_surname: last, first",
        cdb.extract_first_author_surname("Morrison, Douglas Ezra and Smith, Jane") == "Morrison",
    )
    check(
        "author_surname: first last",
        cdb.extract_first_author_surname("Douglas Ezra Morrison and Jane Smith") == "Morrison",
    )
    check(
        "author_surname: von prefix",
        cdb.extract_first_author_surname("van Dijk, Jan and Peterson, B.") == "van Dijk",
    )
    check(
        "author_surname: latex accent",
        cdb.extract_first_author_surname(r"M\"uller, Hans and Bauer, Franz") == "Müller",
    )
    check(
        "author_surname: org in braces",
        cdb.extract_first_author_surname("{World Health Organization}") == "World Health Organization",
    )


def test_parse_bib_entries() -> None:
    bib_text = """
    % A comment line
    @article{morrison2024causal,
      title = {{Causal} Inference for {Observational} Studies},
      author = {Morrison, Douglas E. and Pearl, Judea},
      year = {2024},
      journal = {Journal of Causal Inference},
      doi = {10.1000/182}
    }

    @inproceedings{smith2023deep,
      author = "Smith, Bob and Doe, Jane",
      title = "Deep Learning Methods: A Survey",
      year = "2023",
      booktitle = "NeurIPS",
      doi = "https://doi.org/10.1000/neurips.2023"
    }

    @misc{nodoi2020,
      title = {A Working Paper Without DOI},
      author = {Anonymous, Author},
      year = {2020}
    }
    """

    entries = cdb.parse_bib_entries(bib_text)
    check("parse_bib: entry count", len(entries) == 3)

    e1 = entries[0]
    check("parse_bib: key 1", e1.key == "morrison2024causal")
    check("parse_bib: title 1", e1.title == "Causal Inference for Observational Studies")
    check("parse_bib: author 1", e1.author == "Morrison, Douglas E. and Pearl, Judea")
    check("parse_bib: year 1", e1.year == "2024")
    check("parse_bib: doi 1", e1.doi == "10.1000/182")

    e2 = entries[1]
    check("parse_bib: key 2", e2.key == "smith2023deep")
    check("parse_bib: title 2", e2.title == "Deep Learning Methods: A Survey")
    check("parse_bib: doi 2 normalized", e2.doi == "10.1000/neurips.2023")

    e3 = entries[2]
    check("parse_bib: key 3 no doi", e3.doi is None)


def test_extract_cited_keys() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_file = tmp_path / "paper.tex"
        tex_file.write_text(
            r"""
            \documentclass{article}
            \begin{document}
            As shown in \cite{key1} and \citep{key2, key3}, as well as \autocite{key4}.
            \end{document}
            """,
            encoding="utf-8",
        )

        qmd_file = tmp_path / "chapter.qmd"
        qmd_file.write_text(
            """
            # Chapter
            See [@key5; @key6] for details, or @key7.
            """,
            encoding="utf-8",
        )

        cited = cdb.extract_cited_keys(tmp_path)
        expected = {"key1", "key2", "key3", "key4", "key5", "key6", "key7"}
        check("extract_cited_keys: matched all", cited == expected, f"got {cited}")


def test_fuzzy_match_title() -> None:
    # Exact
    m, s = cdb.fuzzy_match_title("Causal Inference in Statistics", "Causal Inference in Statistics")
    check("fuzzy_title: exact", m and s == 1.0)

    # Subtitle addition/omission
    m, s = cdb.fuzzy_match_title(
        "Causal Inference in Statistics",
        "Causal Inference in Statistics: A Primer",
    )
    check("fuzzy_title: subtitle variation", m and s >= 0.75, f"score: {s}")

    # LaTeX vs Unicode
    m, s = cdb.fuzzy_match_title(
        r"Estimation of Poincar\'e constants",
        "Estimation of Poincaré constants",
    )
    check("fuzzy_title: latex accent", m and s >= 0.95, f"score: {s}")

    # Completely different
    m, s = cdb.fuzzy_match_title(
        "Causal Inference in Statistics",
        "Deep Reinforcement Learning for Robotics",
    )
    check("fuzzy_title: mismatch", not m, f"score: {s}")


def test_fuzzy_match_author() -> None:
    # Exact
    m, s = cdb.fuzzy_match_author("Morrison, Douglas", "Morrison")
    check("fuzzy_author: exact", m and s == 1.0)

    # Accent tolerance
    m, s = cdb.fuzzy_match_author(r"M\"uller, Hans", "Muller")
    check("fuzzy_author: accent normalization", m and s >= 0.90, f"score: {s}")

    # Different author
    m, s = cdb.fuzzy_match_author("Morrison, Douglas", "Johnson")
    check("fuzzy_author: mismatch", not m, f"score: {s}")


def test_mock_resolver_verification() -> None:
    # Mock resolver database
    mock_db = {
        "10.1000/match": cdb.ResolvedMetadata(
            doi="10.1000/match",
            title="Causal Inference in Statistics",
            first_author_family="Morrison",
            year="2024",
            status=cdb.CheckStatus.MATCH,
            source="crossref",
        ),
        "10.1000/fabricated": cdb.ResolvedMetadata(
            doi="10.1000/fabricated",
            title="Unrelated Paper on Quantum Physics",
            first_author_family="Planck",
            year="1900",
            status=cdb.CheckStatus.MATCH,
            source="crossref",
        ),
        "10.1000/notfound": cdb.ResolvedMetadata(
            doi="10.1000/notfound",
            status=cdb.CheckStatus.NOT_RESOLVED,
            error_message="HTTP 404",
        ),
        "10.1000/netfail": cdb.ResolvedMetadata(
            doi="10.1000/netfail",
            status=cdb.CheckStatus.UNVERIFIABLE,
            error_message="Connection timed out",
        ),
    }

    def mock_resolver(doi: str) -> cdb.ResolvedMetadata:
        return mock_db.get(
            doi,
            cdb.ResolvedMetadata(
                doi=doi,
                status=cdb.CheckStatus.NOT_RESOLVED,
                error_message="Unknown DOI",
            ),
        )

    bib_sample = """
    @article{valid_paper,
      title = {Causal Inference in Statistics},
      author = {Morrison, Douglas Ezra},
      year = {2024},
      doi = {10.1000/match}
    }

    @article{hallucinated_doi,
      title = {Epidemiological Methods for Surveillance},
      author = {Morrison, Douglas Ezra},
      year = {2024},
      doi = {10.1000/fabricated}
    }

    @article{dead_doi,
      title = {A Lost Study},
      author = {Smith, John},
      year = {2021},
      doi = {10.1000/notfound}
    }

    @article{unverifiable_entry,
      title = {Network Glitch Study},
      author = {Doe, Jane},
      doi = {10.1000/netfail}
    }

    @article{no_doi_entry,
      title = {Book Chapter},
      author = {Brown, Charlie}
    }
    """

    summary = cdb.check_bib(bib_sample, resolver=mock_resolver)
    check("mock_check: total entries", summary.total_entries == 5)
    check("mock_check: matches", summary.matches == 1)
    check("mock_check: mismatches (fabrication)", summary.mismatches == 1)
    check("mock_check: not resolved", summary.not_resolved == 1)
    check("mock_check: unverifiable", summary.unverifiable == 1)
    check("mock_check: no doi", summary.no_doi == 1)
    check("mock_check: has defects", summary.has_defects is True)

    # Scoped check with cited_keys
    summary_scoped = cdb.check_bib(
        bib_sample,
        resolver=mock_resolver,
        cited_keys={"valid_paper", "no_doi_entry"},
    )
    check("mock_check_scoped: matches", summary_scoped.matches == 1)
    check("mock_check_scoped: skipped", summary_scoped.skipped == 3)
    check("mock_check_scoped: has defects", summary_scoped.has_defects is False)


def test_cli_execution() -> None:
    script_path = REPO / "scripts" / "check_doi_bib.py"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        clean_bib = tmp_path / "clean.bib"
        clean_bib.write_text(
            """
            @article{entry1,
              title = {An Entry Without DOI},
              author = {Author, One},
              year = {2020}
            }
            """,
            encoding="utf-8",
        )

        res = subprocess.run(
            [sys.executable, str(script_path), str(clean_bib), "--json"],
            capture_output=True,
            text=True,
        )
        check("cli: clean bib exit 0", res.returncode == 0)
        data = json.loads(res.stdout)
        check("cli: json valid", data["total_entries"] == 1 and data["no_doi"] == 1)

        # Missing target exit 2
        res_missing = subprocess.run(
            [sys.executable, str(script_path), str(tmp_path / "nonexistent.bib")],
            capture_output=True,
            text=True,
        )
        check("cli: missing file exit 2", res_missing.returncode == 2)


def main() -> int:
    test_clean_latex()
    test_normalize_doi()
    test_extract_first_author_surname()
    test_parse_bib_entries()
    test_extract_cited_keys()
    test_fuzzy_match_title()
    test_fuzzy_match_author()
    test_mock_resolver_verification()
    test_cli_execution()

    print(f"\nResults: {passes} passed, {failures} failed")
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
