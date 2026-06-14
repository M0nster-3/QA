---
name: M0-05-product-provenance
description: "模块 0 产出 module0_provenance.json（溯源地图）时加载——即 Step C 执行时。涵盖字段规范、locator 随输入格式自适应（纯文本/md→line）。"
---

# 产物：module0_provenance.json

## 用途

切块溯源地图。每个 md 一条记录，定位回原始输入的位置。**只给人/前端核对**，不进下游流水线。为什么：provenance 是审计用的元数据，不是流水线功能依赖——它记载"这条 md 从原文哪里来"，供人类检查核对。

## 字段

```yaml
- md_file: "thm_00012.md"
  file: "paper.md"
  locator:
    type: "line"        # line（纯文本/md）
    value: "142-178"
```

| 字段 | 填法 |
|------|------|
| md_file | 产出的 md 文件名 |
| file | 原始输入文件名，固定 "paper.md" |
| locator.type | 纯文本/Markdown → "line"。type 封闭为 "line"，不要其他值。为什么：M0 输入是 paper.md（markdown 文件），定位单元始终是行号 |
| locator.value | 单值（"48"）或区间（"48-49"、"120-145"） |

type 封闭成 "line" 一个值。为什么：封闭枚举值让前端和审核工具能可靠解析——多一个值意味着多一个处理分支。
