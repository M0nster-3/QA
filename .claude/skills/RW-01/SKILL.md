---
name: RW-01-rewrite
description: "将论文 PDF 逐页转为干净 markdown。当需要读取 PDF 并转写为 paper.md、看到 PDF 输入、或被告知「转为 markdown」时加载。多模态逐页读取，数学公式反向识别为 LaTeX，定理/定义用 **Type Number.** 标记。注意：产物只写格式的红线自查见 RW-RF-paper。"
---

# 产物：paper.md

## 用途

将论文 PDF 逐页转为一份自包含的干净 markdown 文件，供下游处理。

## 总则

保留论文全文——动机叙述、历史背景、章节前言、数学内容全部转录。不做取舍。paper.md 是论文的完整 markdown 版本。

## 工作流程

1. 用 Read 工具打开 PDF，逐页读取
2. 每页的内容转为标准 markdown
3. 写入 paper.md

## 转写规则

### 数学公式

PDF 中渲染的数学公式，我需要**反向识别**并写为 LaTeX 数学语法。使用 `$...$`（行内）和 `$$...$$`（独立行）包裹。为什么：下游 MathJax 渲染需要标准 LaTeX 语法，非标准写法会显示错误。

视觉识别 → LaTeX 规则：

| 看到 | 写为 |
|------|------|
| 行内变量/符号 | `$x$`, `$\alpha$`, `$\mathbb{R}$` |
| 独立公式 | `$$...$$` |
| 多行对齐公式 | `$$\begin{aligned}...\end{aligned}$$` |
| 分段函数 | `$$\begin{cases}...\end{cases}$$` |
| 上/下标 | `$x^2$`, `$a_i$` |
| 分式 | `$\frac{a}{b}$` |
| 求和/积分 | `$\sum$`, `$\int$` |
| 希腊字母 | `$\alpha$`, `$\beta$`, `$\Gamma$` 等 |
| 黑板粗体 | `$\mathbb{R}$`, `$\mathbb{N}$`, `$\mathbb{C}$` |
| 花体 | `$\mathcal{F}$`, `$\mathcal{M}$` |
| 粗体 | `$\mathbf{x}$`, `$\boldsymbol{\mu}$` |

**关键**：反向识别要准确。PDF 中 `ℝ` 是 `$\mathbb{R}$`，`𝒞` 是 `$\mathcal{C}$`，不是随意猜测。猜错一个符号可能改变数学含义——这违反宪法铁律。

### 文本结构

| 看到 | 写为 |
|------|------|
| 论文标题 | `# Title` |
| 作者信息 | `**Author Names**` + 机构 |
| 一级标题（如 "1. Introduction"） | `## 1. Introduction` |
| 二级标题（如 "2.1 Preliminaries"） | `### 2.1 Preliminaries` |
| 定理环境 | `**Theorem X.Y.** statement` |
| 引理环境 | `**Lemma X.Y.** statement` |
| 定义环境 | `**Definition X.Y.** statement` |
| 命题环境 | `**Proposition X.Y.** statement` |
| 推论环境 | `**Corollary X.Y.** statement` |
| 注记环境 | `**Remark X.Y.** statement` |
| 证明块 | `*Proof.* ...` |
| 无序列表 | `- item` |
| 有序列表 | `1. item` |
| 引用编号 | `[N]`（保持 PDF 中的编号） |
| 引用列表 | `## References` + `[N] Author, Title, Journal/Publisher, Year` |
| 脚注 | `[^N]: text` |
| 表格 | markdown table（`| col | col |`） |
| 图片标题 | `*Figure N: caption*` |

### 结构化标记

定理/定义/引理等**必须用 `**Type Number.**` 格式**标记。为什么：下游 M0 Agent 需要靠这个格式识别和切分数学结构。

```markdown
**Theorem 2.1.** Let X be a compact metric space...
**Definition 3.5.** A function f is called...
**Lemma 4.2.** For any ε > 0...
*Proof.* The proof proceeds by...
```

## 注意

我只处理当前 PDF 片段。不需要写 checkpoint，不需要续跑。完成当前片段后停止。
