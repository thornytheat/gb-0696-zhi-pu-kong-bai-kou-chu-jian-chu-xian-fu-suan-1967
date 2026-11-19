from collections import Counter
from app.report import report

DETECTION={"PASS":"检出","BELOW_LOD":"未检出","NEGATIVE_BLANK":"低于空白","OVER_RANGE":"超曲线范围","CONTROL_FAIL":"质控超限"}
VERDICT_LABEL={"ISSUABLE":"可签发","FIELD_BLANK_EXCEEDED":"不可签发·现场空白超限","TRANSPORT_BLANK_EXCEEDED":"不可签发·运输空白超限","FIELD_BLANK_MISSING":"不可签发·空白来源未分清","NOT_APPLICABLE":"不适用"}

def ready(rows,errors):
    return bool(rows) and not errors and not any(r["status"] in {"OVER_RANGE","CONTROL_FAIL"} for r in rows)

def verdict(row,groups):
    if row["kind"]!="sample":return "NOT_APPLICABLE"
    field=groups.get("field")
    if field is None:return "FIELD_BLANK_MISSING"
    if field["value"]>field["limit"]:return "FIELD_BLANK_EXCEEDED"
    transport=groups.get("transport")
    if transport is not None and transport["value"]>transport["limit"]:return "TRANSPORT_BLANK_EXCEEDED"
    return "ISSUABLE"

def apply(ctx):
    bykey={}
    for g in ctx["blank_groups"]:bykey.setdefault((g["batch"],g["analyte"]),{})[g["type"]]=g
    final=[]
    for r in ctx["quality"]:
        key=(r["batch"],r["analyte"]);groups=bykey.get(key,{});curve=ctx["curves"].get(key,{})
        code=verdict(r,groups)
        x=dict(r)
        x["detection"]=DETECTION.get(r["status"],r["status"])
        x["field_verdict"]=code;x["field_verdict_label"]=VERDICT_LABEL[code]
        for btype in ("equipment","transport","field"):
            x["blank_"+btype]=groups[btype]["value"] if btype in groups else None
        x["basis"]={"blank_basis":ctx.get("blank_basis","equipment"),
                    "curve":{"slope":curve.get("slope"),"intercept":curve.get("intercept"),"r2":curve.get("r2")},
                    "blank_lines":{btype:groups[btype]["lines"] for btype in groups}}
        final.append(x)
    ctx["final"]=final;ctx["blocked"]=not ready(final,ctx["curve_errors"])
    excluded={r["line"] for r in ctx["quarantine"]}
    accepted=ctx["input_count"]-len(excluded)-ctx["blank_rows"]
    ctx["balance"]={"input":ctx["input_count"],"accepted":accepted,"quarantined":len(excluded),"blank":ctx["blank_rows"]}
    conclusions=dict(Counter(x["field_verdict"] for x in final))
    ctx["conclusions"]=conclusions
    blocked=sum(v for k,v in conclusions.items() if k not in {"ISSUABLE","NOT_APPLICABLE"})
    return report(final,结论="阻断" if ctx["blocked"] else "可复核",样品=len(final),隔离=len(excluded),可签发=conclusions.get("ISSUABLE",0),不可签发=blocked)
