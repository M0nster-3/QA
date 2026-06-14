---
name: M0-02-product-md-yaml
description: "模块 0 产出 md+YAML 文件时加载——即 Step A 执行时。涵盖文件粒度、命名、YAML 字段、kind 判定技艺（11 类封闭集的逐类判据与易混边界）、正文约定、Statement/Proof 分界、取舍规则、无标记文本的切块方法。注意：paper.md 已预处理为干净 markdown，M0 不需要处理 LaTeX 排版转换；convention 不产 md（见 M0-03）；索引表规范见 M0-06；溯源见 M0-05。"
---

# 产物：MD+YAML

## 文件粒度与命名

- 每个 .md 只含一种 kind，但可容纳多个同种结构（一段连续定义文字里多个术语 → 一个 def md，不按术语拆、不判"派生"）。为什么：同种连续结构共享上下文，拆散会丢失语义连贯性。
- 不同 kind 不混入同一 md。为什么：不同 kind 对应不同的语义角色和下游处理，混入会破坏依赖图的类型安全。
- convention 不产 md（进 scope.json）。
- 命名：`<缩写>_<5位流水号>.md`，全局唯一，不含原文编号。为什么：流水号保证确定性排序和断点续传；不含原文编号是因为编号可能重复（如多个 Lemma 2.1 来自不同章节）。

缩写表：def/thm/lem/prop/cor/rem/eg/ex/not/conv/ax。

## MD 文件结构

```
---
kind: <11类之一>
label: "<原文字面编号或空>"
has_proof: true|false
proof_omitted_by_source: true|false
certainty_answer: true|false
---

## Statement
<陈述正文>

## Proof
<证明正文，无证明则留空>
```

## YAML 字段

| 字段 | 填法 |
|------|------|
| kind | 从 11 类封闭集选，见下方判定技艺 |
| label | 从 paper.md 文本中提取编号（如 "**Theorem 2.1.**" → `"Theorem 2.1"`）。无编号则 `""`。为什么：paper.md 中所有引用已解析为可读编号，label 就在文本里，不需要再查表 |
| has_proof | 原文给出证明文字 = true，否则 false |
| proof_omitted_by_source | 原文主动声明省略（"proof omitted"等）= true；"显然" = true；其余 = false。为什么："省略"和"显然"是作者声明——下游据此判断该结论是否有已知证明支撑 |
| certainty_answer | 该条目的结论是否包含一个完全确定的、唯一的答案，见下方判定 |

## kind 判定技艺

### definition
规定一个术语/概念的含义。标志："is called"、"is defined as"、"we say"、"A ... is a ..."。一段里多个概念（如 topological space + open + closed + G_δ + F_σ）整段进一个 def md。为什么：这些概念互相定义、彼此依赖，拆开会丢失定义之间的引用关系。

### theorem / lemma / proposition / corollary
都是"需证明的断言"，差别在作者给的定位：
- theorem：作者标 Theorem、或全章/全节的核心结论
- lemma：作者标 Lemma、或明确为辅助性的
- proposition：作者标 Proposition、或一般性结论（非核心非辅助）
- corollary：作者标 Corollary、或明确是前述结果的直接推论

**无标记时**按内容角色判：证明短且直接跟在某定理后 → 大概率 corollary；独立篇幅大 → theorem/proposition；前面的大定理证明里抽出来的 → lemma。拿不准在 thm/lem/prop 三者间选，优先 proposition（最中性）。为什么：proposition 是最中性的断言类 kind，不预设核心/辅助定位，拿不准时选它不会过度承诺。

### remark
补充性评注，不是核心待证命题。标志："Note that"、"Observe that"、"It is worth noting"。**remark 不是垃圾桶**——remark 里如果包含了需证明的断言，那个断言要切出来单独成 thm/lem/prop。为什么：把待证命题混入 remark 会丢失依赖边——下游无法得知这个断言依赖什么、被什么依赖。

### example
具体实例（"For example"、"Consider the case"）。和 theorem 的区别：example 举一个具体对象/构造，theorem 陈述一般性命题。

### exercise
留给读者（"Show that"、"Prove that"、"Exercise"）。

### notation
独立的记号约定声明（"We write ∘ for..."、"记作..."）——**不依附于任何 def/thm 的独立声明**才作 notation。记号若长在某 def/thm 正文里（如收敛定义里 "we write p_n → p"），随宿主走、不单独提取。为什么：寄生记号脱离宿主无意义，且宿主 md 的依赖边已覆盖其符号依赖。

### convention
声明某范围内的默认前提（"本章默认 T2"、"throughout this section"）。不产 md，进 scope.json。为什么：convention 是元规则而非数学内容——它不产生新的数学结构，只约束其他结构的解读范围。

### axiom
不证自明的基本假设，作者明确标为 axiom。

### 易混边界速查

| 对比 | 判据 |
|------|------|
| definition vs notation | definition 定义概念含义，notation 规定符号写法。二者可同处一段——定义体内有记号则记号随宿主、不单独切 |
| definition vs convention | definition 定义一个对象，convention 默认一个前提 |
| definition vs theorem | definition 不需证明，theorem 需证明 |
| theorem vs lemma vs proposition | 看作者定位（核心/辅助/一般），无标记优先 proposition |
| corollary vs theorem | corollary 明确是前述结果的推论 |
| remark vs theorem | remark 是评注，若含待证断言则切出来 |
| axiom vs convention | axiom 是"不证自明"，convention 是"默认前提"（可改可撤） |

## certainty_answer 判定

**定义**：该条目的结论是否包含一个完全确定的、唯一的答案——可精确比对。为什么：这个字段供下游做自动化验证——只有确定答案才能写测试用例比对。

**true 的场景**：

| 类型 | 示例 |
|------|------|
| 具体数值 | "$(0,1)$ 的下确界为 $0$" |
| 具体计算结果 | "$\int_0^1 x^2 dx = \frac{1}{3}$" |
| 具体对象 | "满足条件的唯一函数为 $f(x) = e^x$" |
| 是/否判定 | "该空间不是紧的" |
| 显式构造 | "反例为 $X = \{1/n : n \in \mathbb{N}\}$" |
| 明确基数/维数 | "该空间的维数为 $3$" |

**false 的场景**：

| 类型 | 示例 |
|------|------|
| 存在性定理 | "存在满足条件的 $f$"（不指定哪一个） |
| 一般性性质 | "紧度量空间上的连续函数一致连续" |
| 等价刻画 | "$X$ 紧当且仅当每个开覆盖有有限子覆盖" |
| 不等式估计 | "$\|f\| \le C\|g\|$"（$C$ 不确定） |
| 结构定理 | "每个有限生成阿贝尔群同构于..." |

**边界处理**：
- 结论含确定值但证明是一般性推理 → true（以结论的确定性为准）
- 结论是"上确界可以取得"（取得，但没说取多少）→ false
- 拿不准 → false（保守策略）。为什么：false 不会误导下游做错误验证；true 但实际不确定会制造假阳性测试。

## 正文约定

paper.md 已预处理为干净 markdown——无 LaTeX 排版命令残留，`\ref`/`\cite` 已解析为可读引用。

- 数学含义和符号不得改变。推理步骤原样保留，不拆不切。
- 公式：行内 `$...$`，独立行 `$$...$$`，语法 LaTeX。行内长公式提为独立行，原为独立行的保持独立行。目的是人类阅读舒适。
- 有证明：## Proof 填证明正文。
- 无证明：## Proof 段留空（保留标题）。为什么：Proof 段存在（即使为空）让下游统一处理——不需要判断标题是否存在。

## Statement / Proof 分界

- 有标记（"Proof."、"Proof:"）→ 标记前 = Statement，标记后 = Proof。
- 无标记 → Statement 是命题陈述（"Let... Then..."到"."），Proof 是紧随其后的论证文字。如果分不清，整段放 Statement、Proof 留空。为什么：宁可缺证明也不要把陈述正文误切进 Proof。

## 取舍

- **留**：定义、命题、证明、例子、习题、评注、记号约定、全局约定、公理——一切数学内容。
- **丢**：动机叙述、历史背景、教学指导（"students should..."）、章节前言闲话。为什么：这些是写给人类读者的辅助文字，不是可结构化的数学内容。
- **不确定时倾向保留**。为什么：多留一条可以人工剔除，漏切一条不可恢复。

## 无标记文本切块

原文无 Definition/Theorem 等标记时（论文常见），按内容角色识别：
- 看到"is called / is defined as"→ 开始切 definition
- 看到断言性命题（"if...then..."陈述一般性命题）→ 切 theorem/proposition
- 看到论证文字跟在命题后→ 切入 ## Proof
- 看到"we write / 记作"独立一句→ 切 notation
- 看到"本章默认 / throughout this section"→ 记 convention

切块结束标志：下一个结构的开始、或段落自然结束。
