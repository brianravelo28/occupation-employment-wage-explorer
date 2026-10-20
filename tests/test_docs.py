"""Links inside the public docs: every relative link and heading anchor must resolve."""
import re

import pytest

from conftest import ROOT

DOCS = [ROOT / "README.md", *sorted(p for p in (ROOT / "docs").glob("*.md") if p.name != "WALKTHROUGH.md")]  # the walkthrough is local-only
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def slug(heading: str) -> str:
    """GitHub's heading anchor: lowercase, drop punctuation, spaces become hyphens."""
    text = heading.strip().lower().replace("`", "")
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(path):
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m:
            found.add(slug(m.group(1)))
    return found


def internal_links(doc):
    for target in LINK.findall(doc.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        yield target


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_relative_links_and_anchors_resolve(doc):
    for target in internal_links(doc):
        path_part, _, anchor = target.partition("#")
        dest = (doc.parent / path_part).resolve() if path_part else doc
        assert dest.exists(), f"{doc.name}: broken link target {target}"
        if anchor and dest.suffix == ".md":
            assert anchor in anchors(dest), f"{doc.name}: no heading for #{anchor} in {dest.name}"


def test_the_anchors_other_tools_link_to_still_exist():
    methodology = anchors(ROOT / "docs" / "METHODOLOGY.md")
    assert {"cpi-and-jolts", "2020-shock-and-recovery", "florida-vs-national-wages", "known-limitations"} <= methodology


def test_the_slug_function_matches_github_for_a_tricky_heading():
    assert slug("Status & Limitations") == "status--limitations"
    assert slug("`shock_2020_response.csv`") == "shock_2020_responsecsv"
