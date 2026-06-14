---
name: M0-01-workflow
description: "模块 0 的五步轮回执行流程、分批接力机制。当需要了解整体工作顺序、每篇 md 的完整性约束、分批触发条件、接力契约（handoff_state.json）格式时加载。注意：各类产物的字段规范见 M0-02~M0-06，红线自查见 M0-RF-* 系列，convention 处理见 M0-03。"
---

# 工作流程

## 铁律

我处理的最小单位是**一篇 md**。每篇 md 必须先做 kind 预判，再走完以下五步轮回，才能碰下一篇。

```
Step 0: kind 预判  —— 识别数学结构 → 选 kind（11 种封闭集）
                       ↓ 是 convention？
                       ↓ 是 → 走「convention 例外」（见下方），跳过 Step A-E，直接 checkpoint → 下一篇
                       ↓ 否 → 进入五步轮回 ↓
Step A: 写 md         —— 切结构 → 搬运正文 → 填 YAML → Write
Step B: 登记 index     —— label 非空 → Write global_name_index.json（label 为空则跳过）
Step C: 追加 provenance —— Write module0_provenance.json（新增本条，不改已有条目）
Step D: 构建依赖图     —— 查引 + 连边 + 挂 dangling + 反查 scope.json 追加 affected_md → Write project_deps.json
Step E: 写 checkpoint  —— Write .checkpoint（done {serial}）

只有 E 写完后，才能开始下一篇 md 的 Step 0。
```

**每一篇 md 都是独立轮回。** 不允许"先把这一批 md 都写了再统一生成元数据"。为什么：任何一步异常中断时，已完成 md 的元数据是完整的、可用的。批量补写会导致元数据与 md 之间的状态不一致。具体红线见 M0-RF-handoff。

## 六步详解

### Step 0: kind 预判
识别论文中下一个数学结构 → 取舍（数学留、闲话丢）→ 选 kind（11 种封闭集，详见 M0-02 判定技艺）。
- 判定为 **convention** → 跳至下方「convention 例外」，不执行 Step A。
- 非 convention → 进入 Step A。

### Step A: 切出结构 + 写 md
逐字搬运正文。paper.md 中引用（\ref/\eqref）已解析为真实编号，直接搬运即可。label 从 paper.md 文本中显式编号提取（如 `**Theorem 2.1.**` → label=`"Theorem 2.1"`），空 label 不登记 → 分配 id。Write 前读 M0-RF-md。

### Step B: 登记 index
若 label 非空 → Write global_name_index.json（label→id 映射）。label 为空 → 跳过此步。Write 前读 M0-RF-index。为什么：index 是下游解析 "by Lemma 3.1" 这类显式引用的反查表——label 为空的结构无法被显式引用，登记无意义。

### Step C: 追加 provenance
module0_provenance.json 新增一条（md_file, file="paper.md", locator）。不改已有条目。Write 前读 M0-RF-provenance。为什么：provenance 是溯源地图——每条记录独立、只增不改，才能可靠追溯到原文位置。

### Step D: 构建依赖图
查显式引用（paper.md 中的 `**Type Number.**` 或 `[N]` 引用 → 查 index → id）→ 结构性依赖（往前找符号/概念的引入 md，找到就连、找不到不管）→ 连不上的挂 dangling（forward/vague/external，详见 M0-04）。
**此外，反查 module0_scope.json：若本篇 md 落在某 convention 的 literal/semantic 作用域内，追加自己的 id（带 .md 后缀）到该 convention 的 affected_md。** 作用域判定见 M0-03。
Write 前读 M0-RF-deps。

### Step E: 写 checkpoint
写入 `.checkpoint`（`done {serial}`）。Write 前读 M0-RF-handoff。为什么：checkpoint 是分批接力机制的唯一可信进度标记——前台靠它判断是否需要续批、从哪续。

## convention 例外

Step 0 判定为 convention 后：跳过 Step A（不产 md），直接写 module0_scope.json 新增一条（affected_md 暂空——后续每篇 md 在其 Step D 中反查追加），然后写 checkpoint（done {serial}，即便未产 md 也要写），进入下一篇的 Step 0。Write 前读 M0-RF-scope。

## 分批接力

处理过程中若发现 token 将耗尽，在完成当前 md 的五步轮回后产出 handoff_state.json 停止。不要硬撑到截断。为什么：硬撑到截断可能打断当前 md 的轮回（导致元数据不完整），而完成当前轮回后再停保证了每条 md 的完整性。

### handoff_state.json

```yaml
next_serial: "00048"
progress_pointer:
  file: "paper.md"
  locator:
    type: "line"
    value: "520"
  after: "Theorem 3.12 结束处"
```

| 字段 | 作用 |
|------|------|
| next_serial | 下一个流水号起点（5 位零填充），防编号撞车 |
| progress_pointer.file | 原始文件，固定 "paper.md" |
| progress_pointer.locator | 定位（type + value） |
| progress_pointer.after | 原文进度位置，指原文不指产物 |

续批时从 after 之后继续，流水号从 next_serial 开始。已有产物续写不覆盖。
