"""Validation, safe ZIP handling and text extraction. No Streamlit/DB imports (testable)."""
import ast, hashlib, io, posixpath, zipfile

TEXT = {"txt","md","py","java","c","cpp","h","js","ts","tsx","jsx","html","css","json","xml","yaml","yml",
        "sql","sh","go","rs","rb","php","toml","ini","cfg","env","csv","log"}
ALLOWED = TEXT | {"pdf","docx","doc","rtf","jpg","jpeg","png","webp","xlsx","xls","zip"}
BLOCKED = {"exe","dll","so","pyc","class","bin","o","jar","dmg","msi"}
IGNORED_DIRS = {".git","node_modules","__pycache__",".venv","venv","env",".idea",".pytest_cache",".mypy_cache"}
SIGS = {"pdf":[b"%PDF"],"png":[b"\x89PNG"],"jpg":[b"\xff\xd8\xff"],"jpeg":[b"\xff\xd8\xff"],
        "webp":[b"RIFF"],"zip":[b"PK\x03\x04"],"docx":[b"PK\x03\x04"],"xlsx":[b"PK\x03\x04"],
        "doc":[b"\xd0\xcf\x11\xe0"],"xls":[b"\xd0\xcf\x11\xe0"],"rtf":[b"{\\rtf"]}
MAX_TEXT = 2_000_000

class RejectedFile(Exception): pass
class UnsupportedFormat(Exception): pass

def ext(name): return name.rsplit(".", 1)[-1].lower() if "." in name else ""
def sha256(data): return hashlib.sha256(data).hexdigest()

def validate(name, data, max_bytes):
    e = ext(name)
    if e in BLOCKED: raise RejectedFile(f".{e} files are not accepted")
    if e not in ALLOWED: raise RejectedFile(f"Unsupported file type: .{e or '(none)'}")
    if len(data) > max_bytes: raise RejectedFile(f"File exceeds {max_bytes // 1_000_000} MB limit")
    if e in SIGS and not any(data.startswith(s) for s in SIGS[e]):
        raise RejectedFile(f"Content does not match a .{e} file")
    if e in TEXT and b"\x00" in data[:4096]: raise RejectedFile("Binary content in a text-type file")
    return e

def clean_path(raw):
    p = raw.replace("\\", "/")
    if p.startswith("/") or (len(p) > 1 and p[1] == ":"): raise RejectedFile(f"Unsafe path: {raw}")
    n = posixpath.normpath(p)
    if n == ".." or n.startswith("../") or ".." in n.split("/"): raise RejectedFile(f"Path traversal: {raw}")
    return n

def iter_zip(data, max_depth=3, max_files=2000, max_total=500_000_000, _state=None, _depth=0):
    """Yield (path, bytes) for safe entries; nested zips are recursed. Raises RejectedFile on limits."""
    st = _state or {"files": 0, "bytes": 0}
    if _depth > max_depth: raise RejectedFile("ZIP nesting too deep")
    try: zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile: raise RejectedFile("Corrupt ZIP file")
    for info in zf.infolist():
        if info.is_dir(): continue
        path = clean_path(info.filename)
        parts = path.split("/")
        if any(p in IGNORED_DIRS for p in parts[:-1]) or ext(path) in BLOCKED: continue
        st["files"] += 1
        if st["files"] > max_files: raise RejectedFile("ZIP has too many files")
        remaining = max_total - st["bytes"]
        if info.file_size > remaining: raise RejectedFile("ZIP exceeds uncompressed size limit")
        with zf.open(info) as f: content = f.read(remaining + 1)  # real size, not the declared one
        st["bytes"] += len(content)
        if st["bytes"] > max_total: raise RejectedFile("ZIP exceeds uncompressed size limit")
        if ext(path) == "zip":
            for sub, b in iter_zip(content, max_depth, max_files, max_total, st, _depth + 1):
                yield f"{path}/{sub}", b
        else:
            yield path, content

def _py_structure(text):
    tree = ast.parse(text)
    s = {"classes": [], "functions": [], "imports": []}
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef): s["classes"].append(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): s["functions"].append(n.name)
        elif isinstance(n, ast.Import): s["imports"] += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module: s["imports"].append(n.module)
    s["imports"] = sorted(set(s["imports"]))
    return s

def extract(name, data):
    """Returns (text, structure). Raises UnsupportedFormat for formats without an extractor."""
    e = ext(name); structure = {}
    if e in TEXT:
        text = data.decode("utf-8", errors="replace")
        if e == "py":
            try: structure = _py_structure(text)
            except SyntaxError as ex: structure = {"parse_error": str(ex)}
    elif e == "pdf":
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in r.pages)
        structure = {"pages": len(r.pages)}
    elif e == "docx":
        from docx import Document
        d = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in d.paragraphs)
        for t in d.tables:
            for row in t.rows: text += "\n" + " | ".join(c.text for c in row.cells)
    elif e == "xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        lines = []
        for ws in wb.worksheets:
            lines.append(f"# Sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                lines.append(" | ".join("" if v is None else str(v) for v in row))
        text = "\n".join(lines); structure = {"sheets": wb.sheetnames}
    elif e in {"jpg","jpeg","png","webp"}:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        structure = {"width": im.width, "height": im.height, "ocr": "not implemented yet"}
        try: structure["exif"] = {str(k): str(v)[:200] for k, v in (im.getexif() or {}).items()}
        except Exception: pass
        text = ""
    else:
        raise UnsupportedFormat(f"No extractor for .{e} yet (original file is stored)")
    return text.replace("\x00", "")[:MAX_TEXT], structure
