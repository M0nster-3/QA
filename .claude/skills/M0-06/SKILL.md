---
name: M0-06-product-index
description: "模块 0 产出 global_name_index.json（原文名索引表）时加载——即 Step B 执行时。涵盖字段规范、key 格式（Kind + number，Kind 必须来自 11 类封闭集）、非结构过滤规则、边切边登记规则、空 label 处理。注意：只登记结构 label（theorem/lemma/definition 等），不登记 equation/figure/table 的内部 label；不存概念名、不存符号。"
---

# 产物：global_name_index.json

## 用途

原文编号/名称 → 系统 id 的反查表。下游解析显式引用（"by Lemma 3.1"→ 查本表得 id → 连边）靠它。为什么：显式引用是依赖图的主要连边依据——每条 "by Lemma 3.1" 需要快速查到对应 md 的 id。

## 核心约束：只登记结构 label

**本表只登记 kind 属于 11 类封闭集的 label**。equation、figure、table 等非结构 label 不进本表。

**判断方法**：根据 Step 0 的 kind 预判和 paper.md 上下文中 `**Type Number.**` 的 Type 字段。
- Type 为 Definition/Theorem/Lemma/Proposition/Corollary/Remark/Example/Notation/Convention/Axiom → 登记
- Type 为 Equation/Figure/Table 等非结构类型 → **不登记**

**为什么**：下游查询场景是 "by Lemma 3.1" 或 "by Theorem 2.1"——引用必然以结构 Kind 开头。不会有人写 "by Equation 1" 来引用一个定义。登记非结构 label 会污染索引、产生虚假匹配——下游查 "Lemma 3.1" 时不会误匹配到 "Equation 3.1"。

## key 格式

`<Kind> <number>`，Kind 首字母大写，Kind 和 number 之间一个空格：

```json
{
  "Theorem 3.1": "thm_00027",
  "Lemma 2.1": "lem_00014",
  "Definition 2.3": "def_00007",
  "Proposition 3.4": "prop_00051",
  "Corollary 1": "cor_00021",
  "Remark 5.2": "rem_00103"
}
```

**Kind 来源**：Step 0 预判的 kind（11 类封闭集之一），首字母大写写入 key（如 `proposition` → key 中写 `Proposition`）。

**number 来源**：paper.md 中 `**Type Number.**` 的显式编号（如 "3.4"），或从 section 标题推断编号（同 M0-02 的 label 优先级）。

## 边切边登记

每切出一篇 md、分配 id 后，**立刻**把 `label → id` 加进本表（在连边之前——后续 block 才查得到本块）。为什么：如果登记放在连边之后，后续 md 的 Step D 查不到刚登记的 label，会产生本可避免的 forward dangling。

把 label 登入本表后，才用本表反查其他 \ref 的 target id。

## 空 label

原文无编号（label: ""）→ **不进本表**。无编号的结构只能通过 id 直接引用，或通过结构性依赖连边。为什么：空 label 无法形成有效的 key，且无法被显式引用——没人能写 "by " 来引用一个无编号结构。
