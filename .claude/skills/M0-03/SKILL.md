---
name: M0-03-product-scope
description: "模块 0 产出 module0_scope.json 时加载——即 Step D 反查 scope 或 convention 例外写入时。涵盖 convention 捕获机制、字段规范、scope_type 判定、affected_md 逐篇认领规则。注意：notation 不在此机制内——符号依赖走依赖图（见 M0-04）。"
---

# 产物：module0_scope.json

## 用途

捕获全局默认约定（convention）。**notation 不在此机制内**——记号约定的依赖走依赖图（project_deps.json）。为什么：notation 的依赖是结构化的（哪个 md 用到了这个记号），可以精确连边；convention 的作用域是范围的（"本章默认 T2"），需要逐篇认领。

## 字段

```yaml
- entry_type: "convention"
  text: "本章节的拓扑空间默认 T2"    # 约定原文逐字
  scope_type: "literal"              # literal | semantic
  affected_md: ["thm_00011.md"]      # 逐篇认领攒出
  source_location:
    file: "paper.md"
    locator: { type: "line", value: "196-201" }
```

## scope_type 判定

| 值 | 含义 | 怎么填 affected_md |
|---|---|---|
| literal | 文本范围明确（"this chapter"/"this section"/"Theorems 1–5"） | 机械确定：后续 md 落在该范围内就追加。为什么：literal 的边界是客观的（如章节号），可以自动化判定 |
| semantic | 需数学判断（"the following results"/"whenever X is compact"） | 保守认领：只追加能确定的，拿不准的不加，不卡线。为什么：semantic 的边界是主观的——宁可漏认领也不错认领 |

## affected_md 逐篇认领

1. 发现 convention → 记入 scope.json，affected_md 暂空
2. 后续每产出一个 md → 反查 scope.json，落在某 literal 作用域内 → 追加自己 id
3. literal 有客观边界（如"第 3 章"），超出自动不认领
4. semantic 仅追加能确定的，拿不准不加
