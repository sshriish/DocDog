import io, sys, zipfile, pytest
sys.path.insert(0, ".")
from processing import *

def mkzip(entries):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, d in entries: z.writestr(n, d)
    return b.getvalue()

def test_traversal_rejected():
    with pytest.raises(RejectedFile): list(iter_zip(mkzip([("../evil.txt", "x")])))
    with pytest.raises(RejectedFile): list(iter_zip(mkzip([("/abs.txt", "x")])))

def test_ignored_dirs_and_binaries_skipped():
    z = mkzip([("a/ok.py", "x=1"), ("node_modules/p/i.js", "1"), (".git/c", "1"), ("run.exe", "1")])
    assert [p for p, _ in iter_zip(z)] == ["a/ok.py"]

def test_file_count_limit():
    with pytest.raises(RejectedFile): list(iter_zip(mkzip([(f"{i}.txt", "x") for i in range(5)]), max_files=3))

def test_uncompressed_size_limit_bomb():
    with pytest.raises(RejectedFile): list(iter_zip(mkzip([("big.txt", "0" * 100_000)]), max_total=1000))

def test_depth_limit():
    z = mkzip([("a.txt", "x")])
    for _ in range(4): z = mkzip([("n.zip", z)])
    with pytest.raises(RejectedFile): list(iter_zip(z, max_depth=2))

def test_signature_mismatch_and_blocked():
    with pytest.raises(RejectedFile): validate("a.pdf", b"not a pdf", 10**6)
    with pytest.raises(RejectedFile): validate("a.exe", b"MZ", 10**6)
    assert validate("a.pdf", b"%PDF-1.4", 10**6) == "pdf"

def test_python_structure():
    _, s = extract("m.py", b"import os\nclass A: pass\ndef f(): pass\n")
    assert s["classes"] == ["A"] and s["functions"] == ["f"] and s["imports"] == ["os"]

def test_unsupported_reported():
    with pytest.raises(UnsupportedFormat): extract("old.doc", b"x")
