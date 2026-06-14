---
name: M0-RF-deps
description: "红线：project_deps.json 写入前自查。每次 Write deps.json 前必须加载——这是宪法要求的自查步骤，跳过即违规。逐条核对：每个 md 有节点、statement_deps/proof_refs 为数组、dangling 含 ref/type/section/status、无孤立引用。"
---

# 红线：project_deps.json 写入检查

Write 前逐条自查：

- [ ] 每个已产出的 md 在 deps 中有一个节点（即使无任何边）。为什么：缺失节点会破坏依赖图完整性——遍历时遇到 dangling ref 却找不到目标节点会引发下游错误
- [ ] statement_deps 和 proof_refs 为数组（无 null/字符串）
- [ ] 引用所在段分入正确字段：Statement 段引用→statement_deps，Proof 段引用→proof_refs。为什么：statement_deps 影响拓扑排序，proof_refs 只影响证明阶段引用查找——混入会导致排序错误
- [ ] dangling 每条含四个字段：ref（原文字面）、type（forward/vague/external）、section（statement/proof）、status
- [ ] forward/vague 的 status 为 "unresolved"，external 的 status 为完整书目信息
- [ ] 正文中的 [N] 格式外部引用（如 "[9, Equation 3.11]"）已识别为 external dangling
- [ ] 无自环（节点不引用自己）。为什么：自环在数学上无意义——一个结构不能依赖自己
- [ ] 如实连边，不手动删环、不缩图。为什么：环是论文中的正常现象，删边会丢失真实的引用关系
