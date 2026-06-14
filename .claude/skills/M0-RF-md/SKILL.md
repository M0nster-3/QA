---
name: M0-RF-md
description: "红线：md+YAML 写入前自查。每次 Write md 文件前必须加载——这是宪法要求的自查步骤，跳过即违规。逐条核对：kind 在 11 类内、label 从 paper.md 文本提取、has_proof/proof_omitted_by_source 正确、certainty_answer 已填、Statement/Proof 段存在。"
---

# 红线：md+YAML 写入检查

Write 前逐条自查：

- [ ] kind 在 11 类封闭集内（definition/theorem/lemma/proposition/corollary/remark/example/exercise/notation/convention/axiom）。为什么：kind 不在封闭集内会导致前端无法渲染、下游无法分类处理
- [ ] label 从 paper.md 文本提取（如 "**Theorem 2.1.**" → `"Theorem 2.1"`），无编号则为 `""`。为什么：label 不是凭空起的名字——它是原文编号的精确镜像，供 index 反查
- [ ] label 不是 LaTeX 内部名（paper.md 中不该出现 `\label{...}`）
- [ ] has_proof：原文有证明=true，无证明=false
- [ ] proof_omitted_by_source：原文声明省略或"显然"=true，其余=false。为什么："省略"和"显然"是两种不同状态——前者作者知道证明存在但不写，后者作者认为读者能自行补出
- [ ] certainty_answer：确定性答案=true，一般性结论=false，拿不准=false。为什么：false 不会误导下游做错误验证；true 但不确定会制造假阳性
- [ ] `## Statement` 和 `## Proof` 段都存在（Proof 无内容留空但保留标题）。为什么：Proof 段存在让下游统一处理——不需要判断标题是否存在
- [ ] 数学含义和符号未改变，推理步骤原样保留
- [ ] 文件名格式 `<缩写>_<5位流水号>.md`，全局唯一
