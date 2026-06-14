---
name: M0-RF-handoff
description: "红线：checkpoint 写入前 + handoff_state.json 写入前自查。每次 Write checkpoint 或接力文件前必须加载——这是宪法要求的自查步骤，跳过即违规。逐条核对：轮回完整性、next_serial 格式、progress_pointer 结构、夹缝检查。"
---

# 红线：checkpoint + handoff_state.json 写入检查

## 轮回纪律自查（每次 Write checkpoint 前）

写完 Step E 的 `.checkpoint` 之前，确认我在本篇 md 中没有违规：

- [ ] 本篇 md 的 Step A/B/C/D 全部完成后才写 checkpoint？（不是先写几篇 md 再回头补）。为什么：checkpoint 是分批接力机制的唯一可信进度标记——先补 md 再补 checkpoint 会导致异常中断时进度与实际不一致
- [ ] Step B（index）已执行或跳过？（label 为空时跳过是合法的）
- [ ] Step C（provenance）已追加本条记录？
- [ ] Step D（deps）已新增本节点，statement_deps/proof_refs/dangling 全部填好？
- [ ] 上一篇 md 的 checkpoint 已写入？（不存在两篇 md 之间没有 checkpoint）
- [ ] 当前处理的是**一篇 md**，不是"一个 section 的所有定理"或"一批定义"？为什么：多篇合一违反铁律"每篇 md 一个结构"——出错时无法精确回滚
- [ ] **夹缝检查**：当前结构 proof 结束后、下一个 `**标记**` 开始前，是否夹着短结构（`**Remark.**`, `**Example.**`）？尤其 proof 极短（≤2 行）且紧接密集无标记定义时——此处是高频漏扫区。如有，立即回头补提。为什么：短结构夹在两个大结构之间时容易被视觉跳过——proof 很短时注意力惯性会直奔下一个醒目的 `**Theorem**`

以上任何一条为"否"，我已违规。立即回到漏掉的 Step 补写，不要继续。

## handoff_state.json 检查（Write 前）

- [ ] next_serial 为 5 位零填充字符串（如 "00048"），值为当前最大 serial + 1
- [ ] progress_pointer.file 为 "paper.md"
- [ ] progress_pointer.locator.type 为 "line"
- [ ] progress_pointer.locator.value 非空
- [ ] progress_pointer.after 描述了原文进度位置（如 "Theorem 3.12 结束处"）
- [ ] 当前 md 的五步轮回已全部完成才产出此文件。为什么：不完整的轮回意味着当前 md 的元数据可能有缺失——前台续跑时无从得知哪些步骤已执行
