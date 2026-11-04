"""Every figure quoted in the docs is recomputed from the committed data (src/doc_figures.py)."""
import pytest

import doc_figures
from conftest import ROOT

FIGURES = doc_figures.compute()


@pytest.mark.parametrize("label,text,doc", FIGURES, ids=[f[0] for f in FIGURES])
def test_figure_is_quoted_in_the_docs_as_the_data_produce_it(label, text, doc):
    assert text in (ROOT / doc).read_text(encoding="utf-8"), f"{doc} does not quote '{text}' ({label})"


def test_there_are_enough_figures_to_matter():
    assert len(FIGURES) >= 20


def test_signed_uses_a_true_minus_and_an_explicit_plus():
    assert doc_figures.signed(-7.74) == "−7.7%" and doc_figures.signed(0.4) == "+0.4%"
