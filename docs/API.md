# 接口

`POST /api/run`：{"text":"CSV内容"}。同规则版本与输入摘要只产生一条批次，重跑同一文件不新增批次。

`GET/POST /api/1` 至 `/api/7`：独立样例或自定义文件计算。各模块返回 report、quarantine、balance。

`POST /api/review`：id、整数revision、decision取通过或退回。旧版本409；阻断项不能通过。

`POST /api/runs/{id}/blank-basis`：{"basis":"equipment|transport|field|combined","revision":整数}。从留存的原始进样重算结论；依据未覆盖全部检测项时422且原签发结论不变，版本冲突409。成功后以追加层生效，decision回到待复核，原始结论与原始进样保留，可切回equipment恢复。

`GET /api/runs/{id}`：生效结论（含basis与layers）。`GET /api/runs/{id}?view=original`：原始结论与原始进样。

`GET /api/export/{id}`：唯一证据CSV，与复核页同一组生效结论（实验室浓度、检出状态、现场采样链签发），manifest含空白依据与签发统计，blank行记录各来源空白值与行号。

`GET /api/sample`：样例文本，name取instrument或outsourced。`GET /health`：存活检查。

错误：结构/数值422，版本冲突409，不存在404，文件过大413。逐行异常进入quarantine。
