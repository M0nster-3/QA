---
name: M0-RF-provenance
description: "红线：module0_provenance.json 写入前自查。每次 Write provenance.json 前必须加载——这是宪法要求的自查步骤，跳过即违规。逐条核对：每条 md 有记录、md_file 带 .md 后缀、file 为 paper.md、locator type 为 line。"
---

# 红线：module0_provenance.json 写入检查

Write 前逐条自查：

- [ ] 每产出一个 md 立刻追加一条记录（边切边登记）。为什么：不立刻登记则记录顺序可能乱——provenance 按数组顺序对应处理顺序，乱序会误导审计
- [ ] md_file 带 `.md` 后缀（如 `thm_00012.md`）
- [ ] file 为 "paper.md"（M0 的输入文件）
- [ ] locator.type 为 "line"（M0 输入是 markdown 文件，定位单元始终是行号）。为什么：封闭枚举让前端可靠解析——多一个值意味着多一个处理分支
- [ ] locator.value 非空（单值如 "48" 或区间如 "142-178"）
- [ ] 记录数与已产出 md 数一致
