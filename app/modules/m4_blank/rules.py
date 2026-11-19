from statistics import median
from app.report import report,quarantine
from decimal import Decimal

BLANK_KINDS={"blank":"equipment","equipment_blank":"equipment","transport_blank":"transport","field_blank":"field"}
BLANK_TYPES=("equipment","transport","field")
BLANK_BASES=BLANK_TYPES+("combined",)
# 空白限值=方法检出限基准：样品判定为 浓度<0.05×倍数，空白自身倍数在比较中抵消，故统一0.05 ug/L
BLANK_LIMIT=Decimal("0.05")

def corrected(response,curve,blank):
    return (response-curve["intercept"])/curve["slope"]-blank

def group_value(entries,basis):
    if basis=="combined":
        values=[v for g in entries.values() for v in g["values"]]
        return median(values) if values else None
    group=entries.get(basis)
    return median(group["values"]) if group else None

def apply(ctx):
    basis=ctx.get("blank_basis","equipment")
    groups={}
    for r in ctx["normalized"]:
        btype=BLANK_KINDS.get(r["kind"])
        if not btype:continue
        key=(r["batch"],r["analyte"]);curve=ctx["curves"].get(key)
        if not curve:continue
        group=groups.setdefault(key,{}).setdefault(btype,{"values":[],"lines":[]})
        group["values"].append((r["response"]-curve["intercept"])/curve["slope"]);group["lines"].append(r["line"])
    records=[]
    for (batch,analyte),types in sorted(groups.items()):
        for btype in BLANK_TYPES:
            group=types.get(btype)
            if group:records.append({"batch":batch,"analyte":analyte,"type":btype,"value":median(group["values"]),"limit":BLANK_LIMIT,"count":len(group["values"]),"lines":sorted(group["lines"])})
    ctx["blank_groups"]=records
    ctx["blanks"]={key:value for key,entries in groups.items() if (value:=group_value(entries,basis)) is not None}
    out=[]
    for r in ctx["normalized"]:
        if r["kind"] not in {"sample","control"}:continue
        key=(r["batch"],r["analyte"]);curve=ctx["curves"].get(key)
        if not curve:quarantine(ctx,r,"CURVE_MISSING");continue
        if key not in ctx["blanks"]:quarantine(ctx,r,"BLANK_MISSING");continue
        x=dict(r);x["net"]=corrected(r["response"],curve,ctx["blanks"][key]);x["blank_value"]=ctx["blanks"][key];out.append(x)
    ctx["corrected"]=out
    return report(out,样品=len(out),空白组=len(ctx["blanks"]),空白记录=len(records),空白依据=basis)
