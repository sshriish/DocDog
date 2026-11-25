import psycopg, streamlit as st
from psycopg.rows import dict_row
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import processing as P

st.set_page_config(page_title="TechDocs AI", layout="wide")
ph = PasswordHasher()
MAX_BYTES = int(st.secrets.get("MAX_UPLOAD_MB", 25)) * 1_000_000

def q(sql, params=None, one=False):
    try:
        with psycopg.connect(st.secrets["DATABASE_URL"], row_factory=dict_row, connect_timeout=15) as c:
            cur = c.execute(sql, params or {})
            if not cur.description: return None
            return cur.fetchone() if one else cur.fetchall()
    except psycopg.OperationalError as ex:
        st.error("Database connection failed: " + str(ex))
        st.stop()

# ---------- auth ----------
def auth_page():
    st.title("TechDocs AI")
    t1, t2 = st.tabs(["Log in", "Register"])
    with t1:
        e = st.text_input("Email", key="le"); p = st.text_input("Password", type="password", key="lp")
        if st.button("Log in"):
            u = q("select * from users where email=%(e)s", {"e": e.lower().strip()}, one=True)
            try:
                if not u: raise VerifyMismatchError()
                ph.verify(u["password_hash"], p); st.session_state.user = u; st.rerun()
            except VerifyMismatchError: st.error("Invalid email or password")
    with t2:
        n = st.text_input("Name"); e = st.text_input("Email", key="re")
        p = st.text_input("Password (min 10 chars)", type="password", key="rp")
        if st.button("Create account"):
            if len(p) < 10 or "@" not in e: st.error("Valid email and a 10+ character password required")
            elif q("select 1 from users where email=%(e)s", {"e": e.lower().strip()}, one=True): st.error("Email already registered")
            else:
                u = q("insert into users(email,name,password_hash) values(%(e)s,%(n)s,%(h)s) returning *",
                      {"e": e.lower().strip(), "n": n, "h": ph.hash(p)}, one=True)
                st.session_state.user = u; st.rerun()

# ---------- ingest ----------
def ingest(pid, uid, name, data):
    """Returns a short status string. Original is always stored, even if extraction fails."""
    try: e = P.validate(name, data, MAX_BYTES)
    except P.RejectedFile as ex: return f"❌ {name}: {ex}"
    ck = P.sha256(data)
    if q("select 1 from documents where project_id=%(p)s and checksum=%(c)s", {"p": pid, "c": ck}, one=True):
        return f"⚠️ {name}: duplicate of an existing file, skipped"
    status, err, text, struct = "succeeded", None, "", {}
    try: text, struct = P.extract(name, data)
    except P.UnsupportedFormat as ex: status, err = "unsupported", str(ex)
    except Exception as ex: status, err = "failed", f"{type(ex).__name__}: {ex}"
    d = q("""insert into documents(project_id,uploader_id,filename,file_type,size_bytes,checksum,status,error)
             values(%(p)s,%(u)s,%(f)s,%(t)s,%(s)s,%(c)s,%(st)s,%(er)s) returning id""",
          {"p": pid, "u": uid, "f": name, "t": e, "s": len(data), "c": ck, "st": status, "er": err}, one=True)
    q("insert into document_files(document_id,data) values(%(d)s,%(b)s)", {"d": d["id"], "b": data})
    q("insert into document_content(document_id,extracted_text,structure) values(%(d)s,%(t)s,%(j)s)",
      {"d": d["id"], "t": text, "j": psycopg.types.json.Jsonb(struct)})
    return {"succeeded": "✅", "unsupported": "ℹ️", "failed": "❌"}[status] + f" {name}" + (f": {err}" if err else "")

# ---------- pages ----------
def dashboard(u):
    s = q("""select count(distinct p.id) projects, count(d.id) docs,
             coalesce(sum(d.size_bytes),0) bytes,
             count(*) filter (where d.status='succeeded') ok,
             count(*) filter (where d.status in ('failed','unsupported')) bad
             from projects p left join documents d on d.project_id=p.id where p.owner_id=%(u)s""", {"u": u["id"]}, one=True)
    c = st.columns(5)
    for col, (l, v) in zip(c, [("Projects", s["projects"]), ("Documents", s["docs"]),
            ("Storage", f"{s['bytes']/1e6:.1f} MB"), ("Processed", s["ok"]), ("Failed/unsupported", s["bad"])]):
        col.metric(l, v)
    st.subheader("Recent uploads")
    st.dataframe(q("""select d.filename, p.name project, d.status, d.created_at from documents d
        join projects p on p.id=d.project_id where p.owner_id=%(u)s order by d.created_at desc limit 10""", {"u": u["id"]}),
        use_container_width=True)

def upload(u):
    projs = q("select id,name from projects where owner_id=%(u)s order by name", {"u": u["id"]})
    with st.expander("Create project", expanded=not projs):
        n = st.text_input("Project name"); d = st.text_area("Description")
        if st.button("Create") and n.strip():
            try: q("insert into projects(owner_id,name,description) values(%(u)s,%(n)s,%(d)s)", {"u": u["id"], "n": n.strip(), "d": d}); st.rerun()
            except psycopg.errors.UniqueViolation: st.error("You already have a project with that name")
    if not projs: return
    pr = st.selectbox("Project", projs, format_func=lambda x: x["name"])
    files = st.file_uploader("Files or a project ZIP", accept_multiple_files=True)
    if files and st.button("Upload & process"):
        bar = st.progress(0.0)
        for i, f in enumerate(files):
            data = f.getvalue()
            try:
                if P.ext(f.name) == "zip":
                    P.validate(f.name, data, MAX_BYTES * 20)
                    n = 0
                    for path, b in P.iter_zip(data): st.write(ingest(pr["id"], u["id"], path, b)); n += 1
                    st.write(f"📦 {f.name}: {n} files processed")
                else: st.write(ingest(pr["id"], u["id"], f.name, data))
            except P.RejectedFile as ex: st.write(f"❌ {f.name}: {ex}")
            bar.progress((i + 1) / len(files))

def repo(u):
    projs = q("select id,name from projects where owner_id=%(u)s order by name", {"u": u["id"]})
    c1, c2, c3 = st.columns([2, 2, 2])
    pf = c1.selectbox("Project", [None] + projs, format_func=lambda x: "All" if not x else x["name"])
    sf = c2.selectbox("Status", ["any", "succeeded", "failed", "unsupported"])
    text = c3.text_input("Search names or content")
    rows = q("""select d.id,d.filename,d.file_type,d.size_bytes,d.status,d.error,d.created_at,p.name project
        from documents d join projects p on p.id=d.project_id left join document_content c on c.document_id=d.id
        where p.owner_id=%(u)s and (%(p)s::uuid is null or p.id=%(p)s::uuid) and (%(s)s='any' or d.status=%(s)s)
        and (%(t)s='' or d.filename ilike '%%'||%(t)s||'%%' or p.name ilike '%%'||%(t)s||'%%'
             or c.search_vector @@ websearch_to_tsquery('english',%(t)s))
        order by d.created_at desc limit 200""",
        {"u": u["id"], "p": pf["id"] if pf else None, "s": sf, "t": text.strip()})
    st.dataframe([{k: v for k, v in r.items() if k != "id"} for r in rows], use_container_width=True)
    if not rows: return
    sel = st.selectbox("Open document", rows, format_func=lambda r: f"{r['project']} / {r['filename']}")
    if sel["error"]: st.warning(sel["error"])
    full = q("""select f.data, c.extracted_text, c.structure from document_files f join document_content c using(document_id)
                where f.document_id=%(d)s""", {"d": sel["id"]}, one=True)
    st.download_button("Download original", bytes(full["data"]), file_name=sel["filename"].split("/")[-1])
    if full["structure"]: st.json(full["structure"])
    if full["extracted_text"]: st.text_area("Extracted text (preview)", full["extracted_text"][:5000], height=250)
    if st.checkbox("I want to delete this document") and st.button("Delete permanently"):
        q("delete from documents where id=%(d)s", {"d": sel["id"]}); st.rerun()

# ---------- main ----------
if "user" not in st.session_state: auth_page(); st.stop()
u = st.session_state.user
page = st.sidebar.radio("Menu", ["Dashboard", "Upload", "Repository"])
st.sidebar.caption(u["email"])
if st.sidebar.button("Log out"): del st.session_state["user"]; st.rerun()
{"Dashboard": dashboard, "Upload": upload, "Repository": repo}[page](u)
