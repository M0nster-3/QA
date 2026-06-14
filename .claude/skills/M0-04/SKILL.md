---
name: M0-04-product-deps
description: "模块 0 构建 project_deps.json（文档级依赖图）时加载——即 Step D 执行时。涵盖两类边（statement_deps/proof_refs）的分段规则、两类连边依据（显式引用+结构性依赖）、dangling 三类处理、环的处理原则。注意：显式引用靠 global_name_index.json 反查（见 M0-06），convention 作用域走 scope.json（见 M0-03）。"
---

# 产物：project_deps.json

## 用途

记录 md 间直接依赖邻接表。只产结构（节点+边+dangling），不自己做拓扑排序、环检测、forward 回填。为什么：这些操作需要看到全部节点后才能做——分批模式下我一次只能看到当前批次的 md，看不到全局，做了必然不完整。

## 两类边

| 边 | 引用所在段 | 下游用途 |
|---|---|---|
| statement_deps | ## Statement | 陈述层拓扑排序 + import |
| proof_refs | ## Proof | 证明阶段 import 定位，不排序 |

引用/依赖落在哪个段就分入哪个字段——**机械判断**，看引用在 ## Statement 还是 ## Proof。为什么：statement_deps 影响逻辑依赖顺序（A 依赖 B 的定义），proof_refs 只影响证明阶段的引用查找——两者语义不同，混入会导致拓扑排序错误。

## 连边依据

### (i) 显式引用
正文写了 "by Lemma 3.1" → 查 global_name_index.json（编号→id）→ 连边。

### (ii) 结构性依赖
本块用到某上游 md 引入的符号/概念（如定理陈述用了极限符号 →、或用了"超距离空间"这个概念），即使没写 "by 定义 X" → **顺流水线往前判断**：这个符号/概念是前面哪个 md 引入的，找到就连、**找不到就不管交下游**。

不由我判断"什么是基础符号/约定俗成"——论文里什么算基础太主观，我判不了也不该判。交给下游判断。为什么：基础符号的边界是主观的——有人觉得"极限"是基础，有人觉得需要定义。agent 判必然不稳定，不如把原始信息原样传递。

## dangling

连不上的引用挂 dangling，带 ref（原文字面）/ type / section（引用所在段："statement" 或 "proof"）/ status：

### 识别外部引用

paper.md 中 `\cite{key}` 已被转为 `[N]` 格式。在正文中发现 `[N]`、`[N, Equation X]`、`[N, Theorem Y]` 等模式时：
1. 这是一条外部引用 → type 填 `"external"`
2. 查 paper.md 文末 `## References` 段获取该编号对应的完整书目信息 → 填入 status
3. 为什么不连边：外部文献不在本论文的 md 体系中，无法连为 statement_deps 或 proof_refs

**注意**：`[N]` 和 `[N, ...]` 只作为外部引用记录，不尝试在 index 中查找——index 只存内部结构 label。

> 注：`status` 字段对 `forward` 和 `vague` 存状态码 `"unresolved"`，对 `external` 存完整书目信息字符串；两者语义不同但共用同一字段，下游按 `type` 区分解析。

| type | 含义 | section 填法 | 处理 |
|---|---|---|---|
| forward | 编号明确但目标在后面还没处理 | 引用落在 Statement→"statement"，落在 Proof→"proof" | 记录为 forward，全书扫完后由外部回填为正常边 |
| vague | 模糊回指（"by the above"），尽力判断仍无法确定 | 同上 | 留 dangling，不做强行推测。为什么：强行推测会引入错误依赖边——让下游基于错误信息做判断比没有信息更糟 |
| external | 指向系统外文献（"[4, Theorem 2.1]"） | 同上 | 从参考文献列表回填完整书目信息到 status（作者、年份、标题、期刊），如 `"[4] Smith, J. (1999). On hyperfinite equivalence relations. J. Math. Logic, 42, 1-20."` |

## 字段

```yaml
thm_00012:
  statement_deps: ["def_00007"]
  proof_refs: ["lem_00003"]
  dangling: []
thm_00015:
  statement_deps: []
  proof_refs: ["thm_00012"]
  dangling:
    - { ref: "Theorem 4.2", type: "forward", section: "statement", status: "unresolved" }
    - { ref: "combining the above", type: "vague", section: "proof", status: "unresolved" }
    - { ref: "[4, Theorem 2.1]", type: "external", section: "proof", status: "[4] Smith, J. (1999). On hyperfinite equivalence relations. J. Math. Logic, 42, 1-20." }
```

每个 md 在 deps 里有一个节点，即使没有任何边。为什么：缺失节点会破坏依赖图的完整性——遍历依赖图时遇到 dangling ref 却找不到目标节点，会在下游引发错误。

## 环

如实连边，不管环、不缩图、不删边。环检测交给后续处理。为什么：环是数学论文中的正常现象（如两个定理互相引用），agent 不应该擅自修改——删边会丢失真实的引用关系。
