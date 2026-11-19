from app.pipeline import run, sample_text
from app import store
from app.errors import BusinessError
from app.exporter import evidence_csv
from decimal import Decimal
from uuid import uuid4
import pytest

NONCE=uuid4().hex[:8]
def batch_id(tag):
    return f"{tag}{NONCE}"

HEADER="sample_id,kind,analyte,area,internal_area,level,dilution,unit,batch"
ROWS=[
 "C0,standard,Pb,100,100,0,1,ug/L,{b}",
 "C1,standard,Pb,300,100,1,1,ug/L,{b}",
 "C2,standard,Pb,500,100,2,1,ug/L,{b}",
 "C3,standard,Pb,700,100,3,1,ug/L,{b}",
 "E1,equipment_blank,Pb,106,100,0,1,ug/L,{b}",
 "E2,equipment_blank,Pb,108,100,0,1,ug/L,{b}",
 "T1,transport_blank,Pb,104,100,0,1,ug/L,{b}",
 "F1,field_blank,Pb,120,100,0,1,ug/L,{b}",
 "F2,field_blank,Pb,124,100,0,1,ug/L,{b}",
 "W1,sample,Pb,320,100,0,1,ug/L,{b}",
 "W2,sample,Pb,105,100,0,1,ug/L,{b}",
 "QC1,control,Pb,320,100,1,1,ug/L,{b}",
]

def text(batch="B09",*,skip=(),extra=()):
    rows=[r.format(b=batch) for r in ROWS]
    return "\n".join([HEADER]+[r for r in rows if not any(k in r for k in skip)]+[e.format(b=batch) for e in extra])

def row_of(result,sample_id):
    return next(r for r in result["final"] if r["sample_id"]==sample_id)

def test_lab_concentration_deducts_equipment_only():
    r=run(text())
    assert row_of(r,"W1")["concentration"]=="1.065"
    assert row_of(r,"W1")["blank_equipment"]=="0.035"
    assert row_of(r,"W1")["blank_field"]=="0.11"

def test_detection_status_per_sample():
    r=run(text())
    assert row_of(r,"W1")["detection"]=="检出"
    assert row_of(r,"W2")["detection"]=="低于空白"

def test_field_blank_exceeded_not_issuable():
    r=run(text())
    assert row_of(r,"W1")["field_verdict"]=="FIELD_BLANK_EXCEEDED"
    assert row_of(r,"W1")["field_verdict_label"].startswith("不可签发")
    assert r["conclusions"]["FIELD_BLANK_EXCEEDED"]==2

def test_control_not_applicable():
    assert row_of(run(text()),"QC1")["field_verdict"]=="NOT_APPLICABLE"

def test_field_blank_missing_cannot_issue():
    r=run(text(skip=("field_blank",)))
    w1=row_of(r,"W1")
    assert w1["field_verdict"]=="FIELD_BLANK_MISSING"
    assert w1["concentration"]=="1.065"

def test_transport_blank_exceeded():
    r=run(text(skip=("T1,transport","F1,","F2,"),extra=["T1,transport_blank,Pb,140,100,0,1,ug/L,{b}","F1,field_blank,Pb,104,100,0,1,ug/L,{b}"]))
    assert row_of(r,"W1")["field_verdict"]=="TRANSPORT_BLANK_EXCEEDED"

def test_issuable_when_blanks_under_limit():
    r=run(text(skip=("F1,","F2,"),extra=["F1,field_blank,Pb,104,100,0,1,ug/L,{b}"]))
    assert row_of(r,"W1")["field_verdict"]=="ISSUABLE"

def test_injection_basis_kept():
    r=run(text())
    basis=row_of(r,"W1")["basis"]
    assert basis["blank_basis"]=="equipment"
    assert basis["blank_lines"]=={"equipment":[6,7],"transport":[8],"field":[9,10]}
    assert basis["curve"]["slope"]=="2"

def test_plain_blank_kind_still_equipment():
    r=run(sample_text())
    assert row_of(r,"S002")["concentration"]=="2.0"
    assert row_of(r,"S002")["field_verdict"]=="FIELD_BLANK_MISSING"

def test_switch_basis_changes_conclusions():
    saved=store.save(text(batch_id("B10")),run(text(batch_id("B10"))))
    switched=store.switch_basis(saved["id"],saved["revision"],"combined")
    assert switched["basis"]=="combined"
    assert row_of(switched["result"],"W1")["concentration"]=="1.06"
    assert len(switched["layers"])==1 and switched["layers"][0]["basis"]=="combined"

def test_switch_failure_restores_original():
    saved=store.save(text(batch_id("B11"),skip=("field_blank",)),run(text(batch_id("B11"),skip=("field_blank",))))
    before=store.get(saved["id"])
    with pytest.raises(BusinessError,match="空白依据未覆盖"):
        store.switch_basis(saved["id"],saved["revision"],"field")
    after=store.get(saved["id"])
    assert after["revision"]==before["revision"]
    assert after["decision"]==before["decision"]
    assert after["result"]["final"]==before["result"]["final"]
    assert after["layers"]==[]

def test_switch_unknown_basis_rejected():
    saved=store.save(text(batch_id("B12")),run(text(batch_id("B12"))))
    with pytest.raises(BusinessError,match="空白依据无效"):
        store.switch_basis(saved["id"],saved["revision"],"实验室")

def test_switch_stale_revision_rejected():
    saved=store.save(text(batch_id("B13")),run(text(batch_id("B13"))))
    store.switch_basis(saved["id"],saved["revision"],"combined")
    with pytest.raises(BusinessError,match="版本已更新"):
        store.switch_basis(saved["id"],saved["revision"],"combined")

def test_original_preserved_and_recoverable():
    saved=store.save(text(batch_id("B14")),run(text(batch_id("B14"))))
    store.switch_basis(saved["id"],saved["revision"],"combined")
    kept=store.original(saved["id"])
    assert row_of(kept["result"],"W1")["concentration"]=="1.065"
    current=store.get(saved["id"])
    restored=store.switch_basis(saved["id"],current["revision"],"equipment")
    assert row_of(restored["result"],"W1")["concentration"]=="1.065"
    assert len(restored["layers"])==2

def test_switch_resets_decision_for_rereview():
    saved=store.save(text(batch_id("B15")),run(text(batch_id("B15"))))
    reviewed=store.review(saved["id"],saved["revision"],"通过")
    switched=store.switch_basis(saved["id"],reviewed["revision"],"combined")
    assert switched["decision"]=="待复核"

def test_rerun_same_file_no_new_batch():
    a=store.save(text(batch_id("B16")),run(text(batch_id("B16"))));b=store.save(text(batch_id("B16")),run(text(batch_id("B16"))))
    assert a["id"]==b["id"]

def test_export_matches_page_conclusions():
    saved=store.save(text(batch_id("B17")),run(text(batch_id("B17"))))
    switched=store.switch_basis(saved["id"],saved["revision"],"combined")
    csv_text=evidence_csv(switched)
    assert '""blank_basis"": ""combined""' in csv_text
    for row in switched["result"]["final"]:
        if row["kind"]=="sample":
            assert row["field_verdict_label"] in csv_text
            assert row["concentration"] in csv_text

def test_outsourced_sample_file():
    r=run(sample_text("outsourced"))
    w101=row_of(r,"W101");w201=row_of(r,"W201")
    assert w101["field_verdict"]=="FIELD_BLANK_EXCEEDED"
    assert w101["detection"]=="检出"
    assert w201["field_verdict"]=="ISSUABLE"
    assert r["conclusions"]["ISSUABLE"]==2
