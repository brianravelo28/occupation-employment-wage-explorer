"""The record of the raw BLS files the processed tables were built from (data/raw_checksums.txt, src/checksums.py)."""
import hashlib
import re

import pytest

import checksums
from config import DATA_RAW, OEWS_MB3_YEARS, OEWS_YEARS, RAW_CHECKSUMS


def expected_names():
    standard = [f"oews/oesm{year % 100:02d}all.zip" for year in OEWS_YEARS]
    recalculated = [f"oews_mb3/oes_mb3_{year}a.zip" for year in OEWS_MB3_YEARS]
    return sorted(standard + recalculated)


def test_the_list_names_every_archive_the_pipeline_reads_exactly_once():
    lines = [line for line in RAW_CHECKSUMS.read_text(encoding="utf-8").splitlines() if line.strip()]
    names = [line.split(None, 1)[1].lstrip("*") for line in lines]
    assert sorted(names) == expected_names()          # 11 standard archives and the 6 MB3 research-estimate archives
    assert len(set(names)) == len(names) == 17


def test_every_line_is_a_sha256sum_line():
    for line in RAW_CHECKSUMS.read_text(encoding="utf-8").splitlines():
        assert re.fullmatch(r"[0-9a-f]{64} [ *]\S+", line), line      # the format `sha256sum -c` reads


def test_sha256_of_matches_hashlib(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"occupation" * 200_000)             # spans several read blocks
    assert checksums.sha256_of(f) == hashlib.sha256(b"occupation" * 200_000).hexdigest()


def test_a_file_is_reported_as_match_mismatch_unrecorded_or_missing(tmp_path):
    raw = tmp_path / "raw"
    (raw / "oews").mkdir(parents=True)
    good, changed, extra = raw / "oews" / "a.zip", raw / "oews" / "b.zip", raw / "oews" / "c.zip"
    good.write_bytes(b"one")
    changed.write_bytes(b"two, but BLS replaced it")
    extra.write_bytes(b"three")
    recorded = {"oews/a.zip": hashlib.sha256(b"one").hexdigest(), "oews/b.zip": hashlib.sha256(b"two").hexdigest()}
    assert checksums.check_file(good, recorded, raw) == checksums.MATCH
    assert checksums.check_file(changed, recorded, raw) == checksums.MISMATCH
    assert checksums.check_file(extra, recorded, raw) == checksums.UNRECORDED
    assert checksums.check_file(raw / "oews" / "gone.zip", recorded, raw) == checksums.MISSING
    elsewhere = tmp_path / "other.zip"
    elsewhere.write_bytes(b"one")
    assert checksums.check_file(elsewhere, recorded, raw) == checksums.UNRECORDED   # outside data/raw


def test_the_messages_tell_the_reader_what_to_do(tmp_path):
    f = tmp_path / "oesm25all.zip"
    f.write_bytes(b"x")
    assert "differs from the recorded checksum" in checksums.describe(f, checksums.MISMATCH)
    assert "add it" in checksums.describe(f, checksums.UNRECORDED)


@pytest.mark.skipif(not (DATA_RAW / "oews").exists(), reason="the raw BLS files are not in the repo (CI does not have them)")
def test_the_raw_files_on_this_machine_are_the_recorded_ones():
    recorded = checksums.load_recorded()
    for name in expected_names():
        path = DATA_RAW / name
        if path.exists():
            assert checksums.check_file(path, recorded) == checksums.MATCH, name
