"""
Check the raw BLS download files against the SHA-256 values recorded in
data/raw_checksums.txt.

The raw archives are not in the repo (about 1.2 GB), and BLS can revise or replace a
published file, so the processed tables are only reproducible from the files that were
used. data/raw_checksums.txt records those files in the format `sha256sum -c` reads
(`<hash>  <path relative to data/raw>`), one line per file: the 11 standard OEWS archives
(2015-2025) and the 6 MB3 research-estimate archives (2015-2020).

`python src/checksums.py` prints the status of every recorded file. The fetch script calls
`check_file` for each archive it opens.
"""
import hashlib
from pathlib import Path

from config import DATA_RAW, RAW_CHECKSUMS

MATCH, MISMATCH, UNRECORDED, MISSING = "match", "mismatch", "unrecorded", "missing"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_recorded(checksums_file: Path = RAW_CHECKSUMS) -> dict:
    """{path relative to data/raw (forward slashes): sha256}"""
    recorded = {}
    for line in checksums_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(None, 1)
            recorded[name.strip().lstrip("*")] = digest.lower()
    return recorded


def check_file(path: Path, recorded: dict = None, raw_root: Path = DATA_RAW) -> str:
    """Compare one file with the recorded value: match, mismatch, unrecorded or missing."""
    recorded = load_recorded() if recorded is None else recorded
    if not path.exists():
        return MISSING
    try:
        name = path.resolve().relative_to(raw_root.resolve()).as_posix()
    except ValueError:                      # a file outside data/raw cannot be one of the recorded files
        return UNRECORDED
    if name not in recorded:
        return UNRECORDED
    return MATCH if sha256_of(path) == recorded[name] else MISMATCH


def describe(path: Path, status: str) -> str:
    """One line a person can act on."""
    if status == MATCH:
        return f"  {path.name}: matches the recorded checksum"
    if status == MISMATCH:
        return (f"  WARNING {path.name}: differs from the recorded checksum in data/raw_checksums.txt. BLS may have "
                "replaced the file; the processed tables were built from the recorded one. Update the list if this is intended.")
    if status == UNRECORDED:
        return f"  {path.name}: not in data/raw_checksums.txt (sha256 {sha256_of(path)}); add it if the file is part of the build"
    return f"  {path.name}: missing"


if __name__ == "__main__":
    recorded = load_recorded()
    bad = 0
    for name in sorted(recorded):
        path = DATA_RAW / name
        status = check_file(path, recorded)
        print(describe(path, status))
        bad += status in (MISMATCH, MISSING)
    print(f"\n{len(recorded) - bad} of {len(recorded)} recorded files present and matching")
    raise SystemExit(1 if bad else 0)
