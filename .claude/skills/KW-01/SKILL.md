---
name: KW-01-keywords
description: "ai_keywords 提取规则与输出规范。当需要从论文提取 AI 关键词、写入 source.json 的 ai_keywords 字段、或被告知「提取关键词」时加载。涵盖数量（5-15）、粒度（概念级非单词级）、排序（按核心程度 rank）、去重规则。注意：source.json 其他字段不动的红线见 KW-RF-source。"
---

# 产物：ai_keywords 提取

## 输入

读取 paper.md（由 PDF 转写的 clean markdown）。

## 输出格式

读取 source.json → 更新 ai_keywords 字段 → 写回。**其余字段一字不动**。为什么：source.json 的 title/authors/abstract 等字段由数据获取脚本写入，我无权修改，改了会导致数据不一致。

```json
{
  "ai_keywords": [
    { "keyword": "hyperfinite equivalence relation", "rank": 1 },
    { "keyword": "Borel combinatorics", "rank": 2 },
    { "keyword": "marker method", "rank": 3 }
  ]
}
```

## 提取规则

### 数量
5-15 个，视论文内容丰富度而定。短论文（<10 页）取 5-8 个，长论文取 8-15 个。为什么：少于 5 个覆盖不全，多于 15 个稀释了「核心」概念的意义——搜索引擎和聚类算法对过多关键词会产生噪声。

### 粒度
**数学概念级别**。不是单词级别（"Borel"），也不是句子级别（"We prove that every Borel action..."）。为什么：单词级太粗（无法区分不同上下文中的同一单词），句子级太细（无法作为稳定的检索键）。概念级才是可复用的索引单元。

| ❌ 太细（单词级） | ✅ 正确（概念级） | ❌ 太粗（句子级） |
|------|------|------|
| "Borel" | "Borel equivalence relation" | "We prove that every Borel action of a countable group..." |
| "hyperfinite" | "hyperfiniteness" | "The equivalence relation is hyperfinite if..." |
| "amenable" | "amenable group action" | "Amenability implies hyperfiniteness by the Connes-Feldman-Weiss theorem" |

### 排序（rank）
按概念在论文中的**核心程度**排 rank，不是按出现频率。**rank 从 1 起始，连续递增不跳号**。为什么：rank 用于前端排序和搜索权重，跳号或乱序会误导用户对论文主题的判断。

- rank 1-3：主定理直接涉及的核心概念
- rank 4-8：重要辅助概念、主要证明工具
- rank 9-15：次要概念、背景、相关领域

### 判断核心程度的依据
1. 标题和摘要中出现的概念 → 大概率核心
2. 主定理陈述中涉及的概念 → 核心
3. 反复出现（贯穿多个 section）的概念 → 核心或重要
4. 只在某个 lemma 或 example 中出现的 → 次要

### 语言
与论文一致。英文论文出英文关键词，不要翻译。为什么：翻译引入歧义——中文译名不统一（如 "hyperfinite" 可译"超限"或"超有限"），英文原名是学术界的稳定标识符。

### 去重
同一概念的不同表述合并（如 "hyperfinite equivalence relation" 和 "hyperfiniteness" 视为一个概念，选论文最常用的表述）。为什么：重复概念会浪费 rank 位置、制造虚假的搜索匹配。
