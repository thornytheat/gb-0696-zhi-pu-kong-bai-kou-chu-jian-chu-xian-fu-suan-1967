from pathlib import Path
from app.report import plain,reason_counts
from app.errors import BusinessError
from app.modules.m1_intake.rules import apply as stage1
from app.modules.m2_internal.rules import apply as stage2
from app.modules.m3_curve.rules import apply as stage3
from app.modules.m4_blank.rules import apply as stage4
from app.modules.m5_concentration.rules import apply as stage5
from app.modules.m6_quality.rules import apply as stage6
from app.modules.m7_review.rules import apply as stage7

SAMPLES={"instrument":"instrument.csv","outsourced":"outsourced.csv"}

def sample_text(name="instrument"):
    if name not in SAMPLES: raise BusinessError("SAMPLE","样例不存在",404)
    return (Path(__file__).parent.parent/"sample_data"/SAMPLES[name]).read_text(encoding="utf-8-sig")

def run(text,blank_basis="equipment"):
    ctx={"text":text,"quarantine":[],"reports":[],"blank_basis":blank_basis}
    ctx["reports"].append(stage1(ctx))
    ctx["reports"].append(stage2(ctx))
    ctx["reports"].append(stage3(ctx))
    ctx["reports"].append(stage4(ctx))
    ctx["reports"].append(stage5(ctx))
    ctx["reports"].append(stage6(ctx))
    ctx["reports"].append(stage7(ctx))
    ctx.pop("text",None)
    ctx["reasons"]=reason_counts(ctx)
    return plain(ctx)
