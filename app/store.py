import sqlite3, json, hashlib
from datetime import datetime, timezone
from app.config import DATA_DIR, RULE_VERSION
from app.errors import BusinessError
from app.modules.m4_blank.rules import BLANK_BASES

def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"runs.sqlite", timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, decision TEXT NOT NULL DEFAULT '待复核', created TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS run_layers (run_id TEXT NOT NULL, seq INTEGER NOT NULL, basis TEXT NOT NULL, result TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(run_id,seq))")
    columns=[r[1] for r in db.execute("PRAGMA table_info(runs)")]
    if "text" not in columns: db.execute("ALTER TABLE runs ADD COLUMN text TEXT")
    return db

def save(text, result):
    digest=hashlib.sha256((RULE_VERSION+"\n"+text).encode()).hexdigest()
    ident=digest[:16]
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,digest,result,text,created) VALUES(?,?,?,?,?)",(ident,digest,json.dumps(dict(result,rule_version=RULE_VERSION),ensure_ascii=False),text,datetime.now(timezone.utc).isoformat()))
    return get(ident)

def basis_of(result):
    return result.get("blank_basis") or ("equipment" if result.get("rule_version")==RULE_VERSION else "combined")

def get(ident):
    with connect() as db:
        row=db.execute("SELECT * FROM runs WHERE id=?",(ident,)).fetchone()
        if row is None: raise BusinessError("NOT_FOUND","批次不存在",404)
        layers=[dict(r) for r in db.execute("SELECT seq,basis,created FROM run_layers WHERE run_id=? ORDER BY seq",(ident,))]
        current=db.execute("SELECT result FROM run_layers WHERE run_id=? ORDER BY seq DESC LIMIT 1",(ident,)).fetchone() if layers else None
    item=dict(row);item.pop("text",None)
    item["result"]=json.loads(current["result"]) if current else json.loads(item["result"])
    item["rule_version"]=item["result"].get("rule_version","2026.11.18.1")
    item["basis"]=basis_of(item["result"]);item["layers"]=layers
    return item

def original(ident):
    with connect() as db:
        row=db.execute("SELECT * FROM runs WHERE id=?",(ident,)).fetchone()
    if row is None: raise BusinessError("NOT_FOUND","批次不存在",404)
    item=dict(row);item["result"]=json.loads(item["result"])
    item["rule_version"]=item["result"].get("rule_version","2026.11.18.1")
    item["basis"]=basis_of(item["result"]);item["layers"]=[]
    return item

def history():
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT id,revision,decision,created FROM runs ORDER BY created DESC LIMIT 40")]

def review(ident,revision,decision):
    if not isinstance(decision,str) or decision not in {"通过","退回"}: raise BusinessError("DECISION","复核决定无效")
    current=get(ident)
    if decision=="通过" and current["result"].get("blocked"):
        raise BusinessError("BLOCKED","存在阻断项，请先修正数据",409)
    with connect() as db:
        changed=db.execute("UPDATE runs SET revision=revision+1,decision=? WHERE id=? AND revision=?",(decision,ident,revision)).rowcount
        if not changed: raise BusinessError("STALE","版本已更新，请刷新",409)
    return get(ident)

def switch_basis(ident,revision,basis):
    if basis not in BLANK_BASES: raise BusinessError("BASIS","空白依据无效")
    with connect() as db:
        row=db.execute("SELECT text FROM runs WHERE id=?",(ident,)).fetchone()
    if row is None: raise BusinessError("NOT_FOUND","批次不存在",404)
    if not row["text"]: raise BusinessError("TEXT_MISSING","原始进样缺失，无法切换空白依据",409)
    from app.pipeline import run
    derived=run(row["text"],blank_basis=basis)
    covered={(g["batch"],g["analyte"]) for g in derived["blank_groups"] if basis=="combined" or g["type"]==basis}
    needed={(r["batch"],r["analyte"]) for r in derived["normalized"] if r["kind"] in {"sample","control"}}
    missing=needed-covered
    if missing: raise BusinessError("BLANK_BASIS","空白依据未覆盖全部检测项："+"、".join(f"{analyte}@{batch}" for batch,analyte in sorted(missing)))
    with connect() as db:
        changed=db.execute("UPDATE runs SET revision=revision+1,decision='待复核' WHERE id=? AND revision=?",(ident,revision)).rowcount
        if not changed: raise BusinessError("STALE","版本已更新，请刷新",409)
        db.execute("INSERT INTO run_layers(run_id,seq,basis,result,created) VALUES(?,COALESCE((SELECT MAX(seq) FROM run_layers WHERE run_id=?),0)+1,?,?,?)",(ident,ident,basis,json.dumps(dict(derived,rule_version=RULE_VERSION,blank_basis=basis),ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
    return get(ident)
