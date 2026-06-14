---
name: M0-RF-scope
description: "红线：module0_scope.json 写入前自查。每次 Write scope.json 前必须加载——这是宪法要求的自查步骤，跳过即违规。逐条核对：entry_type 为 convention、scope_type 为 literal/semantic、affected_md 含 .md 后缀、source_location 完整、无 notation 混入。"
---

# 红线：module0_scope.json 写入检查

Write 前逐条自查：

- [ ] 每条 entry_type 为 "convention"（notation 不在此文件，走 deps.json）。为什么：notation 的依赖是结构化的（哪个 md 用到了这个记号），可以精确连边——放 deps.json；convention 是范围性约束——放 scope.json
- [ ] scope_type 为 "literal" 或 "semantic"
- [ ] affected_md 中所有 id 带 `.md` 后缀（如 `thm_00011.md`）。为什么：不带后缀会导致前台 backfill 匹配失败——前台按 `.md` 后缀做字符串匹配
- [ ] source_location 含 `file`（应为 "paper.md"）和 `locator`（type + value）
- [ ] text 为约定原文逐字，未改动
- [ ] semantic 类只追加能确定的 md，拿不准的不加。为什么：semantic 的边界是主观的——宁可漏认领也不错认领
- [ ] 无 convention 之外的条目类型
