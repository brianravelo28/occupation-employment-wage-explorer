"""Every figure quoted in the docs is recomputed from the committed data (src/doc_figures.py)."""
import pytest

import doc_figures
from conftest import ROOT

FIGURES = doc_figures.compute()


@pytest.mark.parametrize("label,text,doc", FIGURES, ids=[f[0] for f in FIGURES])
def test_figure_is_quoted_in_the_docs_as_the_data_produce_it(label, text, doc):
    assert text in (ROOT / doc).read_text(encoding="utf-8"), f"{doc} does not quote '{text}' ({label})"


def test_there_are_enough_figures_to_matter():
    assert len(FIGURES) >= 35


def test_the_weighted_median_agrees_with_the_dashboards(dashboard):
    import pandas as pd

    values, weights = pd.Series([1.0, 2.0, 3.0, 10.0]), pd.Series([5.0, 1.0, 1.0, 3.0])
    assert doc_figures.weighted_median(values, weights) == pytest.approx(dashboard.weighted_quantile(values, weights, 0.5))
