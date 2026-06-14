---
name: M0-RF-index
description: "红线：global_name_index.json 写入前自查。每次 Write index.json 前必须加载——这是宪法要求的自查步骤，跳过即违规。逐条核对：只登记结构 label（11 类 Kind）、无 Equation/Figure/Table key、key 格式 Kind+number、无空 label 条目、无重复 key。"
---

# 红线：global_name_index.json 写入检查

Write 前逐条自查：

- [ ] 所有 key 以 11 类 Kind 开头（Theorem/Lemma/Definition/Proposition/Corollary/Remark/Example/Exercise/Notation/Convention/Axiom）。为什么：下游解析 "by Lemma 3.1" 时按 Kind 前缀做匹配，非标准 Kind 无法匹配
- [ ] 无 Equation/Figure/Table 等非结构 key（Step 0 kind 预判时已过滤，非 11 类不进本表）。为什么：不会有人写 "by Equation 1" 来引用一个定义——非结构 label 只会制造虚假匹配
- [ ] key 格式为 `<Kind> <number>`（Kind 首字母大写，中间一个空格）。为什么：格式不一致会导致字符串匹配失败——下游靠精确的 key 字符串做反查
- [ ] 无空 label 条目（label="" 的 md 不进本表）。为什么：空 label 无法形成有效的 key，也无法被显式引用
- [ ] 无重复 key。为什么：重复 key 意味着两个不同 id 对应同一个 label——下游查 "Theorem 2.1" 时不知道该取哪个
- [ ] 每产出一个 md 后立刻登记（边切边登记，在连边之前）。为什么：登记在连边之后会导致后续 md 的 Step D 查不到刚登记的 label
- [ ] value 为系统 id（`<缩写>_<5位流水号>`），不带 `.md` 后缀。为什么：deps.json 中的 statement_deps/proof_refs 存的是不带后缀的 id——index 的 value 必须与 deps 的引用格式一致
