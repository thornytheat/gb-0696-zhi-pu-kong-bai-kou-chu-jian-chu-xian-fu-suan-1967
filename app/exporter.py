import csv,io,json

def evidence_csv(run):
    out=io.StringIO();writer=csv.writer(out)
    writer.writerow(["run_id","sha256","rule_version","kind","line","reason","conclusion","evidence"])
    writer.writerow([run["id"],run["digest"],run["rule_version"],"manifest","","","",json.dumps({"balance":run["result"]["balance"],"decision":run["decision"],"revision":run["revision"],"blank_basis":run.get("basis",""),"conclusions":run["result"].get("conclusions",{})},ensure_ascii=False)])
    for row in run["result"].get("final",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"result",row.get("line",""),row.get("status",""),row.get("field_verdict_label",""),json.dumps(row,ensure_ascii=False)])
    for row in run["result"].get("blank_groups",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"blank",row.get("lines",[""])[0],row.get("type",""),"",json.dumps(row,ensure_ascii=False)])
    for row in run["result"].get("quarantine",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"quarantine",row.get("line",""),row["reason"],"",json.dumps(row,ensure_ascii=False)])
    return "\ufeff"+out.getvalue()
