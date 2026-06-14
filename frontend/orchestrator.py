"""
离线层编排器 · orchestrator.py

一篇论文 = 三次独立的 claude-agent-sdk 调用：
  Step 2: Rewrite Agent → PDF（分块并发）→ paper.md
  Step 3: KW Agent      → paper.md → ai_keywords → source.json
  Step 4: M0 Agent      → paper.md → 结构化 md + 五份元数据

前台负责：PDF 分块调度、并发 RW Agent、merge、分批接力、后处理。
"""

import os, sys, shutil, json, asyncio, time, re
from pathlib import Path

from dotenv import load_dotenv
_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / ".env"
if not _env_path.exists():
    _example = _project_root / ".env.example"
    if _example.exists():
        shutil.copy(_example, _env_path)
        print(f"📋 已创建 {_env_path}（从 .env.example 复制）")
        print(f"   请在 {_env_path} 中填写你的 API Key 后重新运行")
        sys.exit(0)
load_dotenv(_env_path)

from claude_agent_sdk import query
from claude_agent_sdk.types import ClaudeAgentOptions

# ── 路径常量 ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DATA_DIR = PROJECT_ROOT / "server" / "data" / "papers"

# ── Rewrite Agent 可见 Skill 列表 ───────────────────────────
RW_SKILLS = ["RW-01", "RW-RF-paper"]

# ── M0 Agent 可见 Skill 列表 ────────────────────────────────
M0_SKILLS = [
    "M0-01", "M0-02", "M0-03", "M0-04", "M0-05", "M0-06",
    "M0-RF-md", "M0-RF-scope", "M0-RF-deps",
    "M0-RF-provenance", "M0-RF-index", "M0-RF-handoff",
]

# ── token 阈值 ─────────────────────────────────────────────
TOKEN_THRESHOLD = 0.4               # 40% 时触发分批
MODEL_CONTEXT_LIMIT = 200_000


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _usage_val(u, key: str) -> int:
    """从 usage 对象（dict 或 typed object）中安全取值。"""
    if isinstance(u, dict):
        return u.get(key, 0)
    return getattr(u, key, 0)


def _usage_from_event(raw: dict) -> tuple[int, int]:
    """从 StreamEvent 的原始 event dict 中提取 (input_tokens, output_tokens)。"""
    if "usage" not in raw:
        return 0, 0
    u = raw["usage"]
    inp = _usage_val(u, "input_tokens") or _usage_val(u, "inputTokenCount")
    out = _usage_val(u, "output_tokens") or _usage_val(u, "outputTokenCount")
    return inp, out


def get_env() -> dict[str, str]:
    """获取 agent 子进程需要的环境变量（KW + M0 用 DS）。"""
    return {
        "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", ""),
        "ANTHROPIC_MODEL": os.environ.get("ANTHROPIC_MODEL", ""),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL", ""),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", ""),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", ""),
    }


def get_env_rw() -> dict[str, str]:
    """Rewrite Agent 专用环境——走火山多模态模型。"""
    model = os.environ.get("RW_ANTHROPIC_MODEL", "")
    return {
        "ANTHROPIC_AUTH_TOKEN": os.environ.get("RW_ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_BASE_URL": os.environ.get("RW_ANTHROPIC_BASE_URL", ""),
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
    }


# ═══════════════════════════════════════════════════════════════
# DocPaths — 论文输出路径集中管理
# ═══════════════════════════════════════════════════════════════

class DocPaths:
    """一篇论文对应的所有输出路径。"""
    def __init__(self, paper_dir: Path):
        self.paper_dir = paper_dir
        self.pdf = paper_dir / "paper.pdf"                 # RW 输入：arxiv PDF
        self.source_json = paper_dir / "source.json"       # KW 输出（只填 ai_keywords）
        self.paper_md = paper_dir / "paper.md"             # RW 输出 → KW/M0 输入
        self.output_dir = paper_dir / "processed"
        self.md_dir = self.output_dir / "md"
        self.checkpoint = self.output_dir / ".checkpoint"
        self.handoff = self.output_dir / "handoff_state.json"
        self.index = self.output_dir / "global_name_index.json"
        self.provenance = self.output_dir / "module0_provenance.json"
        self.scope = self.output_dir / "module0_scope.json"
        self.deps = self.output_dir / "project_deps.json"


# ═══════════════════════════════════════════════════════════════
# handoff 自构造（agent 未产出时从 checkpoint 反推）
# ═══════════════════════════════════════════════════════════════

def build_handoff_from_checkpoint(dp: DocPaths) -> dict | None:
    """
    当 agent 未写 handoff_state.json 但 checkpoint 存在时，
    从 provenance.json 取最后一条记录构造接力状态。
    解析失败返回 None。
    """
    try:
        cp_text = dp.checkpoint.read_text(encoding="utf-8").strip()
        parts = cp_text.split()
        serial = parts[-1] if len(parts) >= 2 else cp_text
        next_serial = str(int(serial) + 1).zfill(5)
    except (ValueError, OSError):
        return None

    if dp.provenance.exists():
        try:
            prov = json.loads(dp.provenance.read_text(encoding="utf-8"))
            if prov:
                last = prov[-1]
                return {
                    "next_serial": next_serial,
                    "progress_pointer": {
                        "file": last.get("file", "paper.md"),
                        "locator": last.get("locator", {"type": "line", "value": "?"}),
                        "after": f"{last.get('md_file', '?')} 结束处",
                    },
                }
        except (KeyError, IndexError, json.JSONDecodeError):
            pass  # 解析失败 → 落入下方 fallback

    return {
        "next_serial": next_serial,
        "progress_pointer": {
            "file": "paper.md",
            "locator": {"type": "line", "value": "?"},
            "after": f"checkpoint {serial} 之后",
        },
    }


# ═══════════════════════════════════════════════════════════════
# Prompt 拼接
# ═══════════════════════════════════════════════════════════════

def build_kw_prompt(paper_md_path: str, source_json: str) -> str:
    return f"""你的任务：从以下论文中提取 AI 关键词。

论文文件：{paper_md_path}
输出目标：更新 {source_json} 的 ai_keywords 字段，其余字段不动。

读取论文全文，按 KW-01 SKILL 的规则提取关键词并写入 source.json。
"""


def build_rw_prompt(pdf_path: str, output_path: str) -> str:
    """Rewrite Agent：读一个 PDF chunk → Markdown chunk。"""
    return f"""你的任务：将论文 PDF 转为干净的 markdown。

PDF 文件：{pdf_path}
输出文件：{output_path}

按 RW-01 SKILL 的规则执行转换：
1. 使用 Read 工具逐页读取 PDF
2. 将每页内容转为标准 markdown，保留全部数学公式（LaTeX/MathJax 格式）
3. 识别并保留论文结构：标题、作者、摘要、章节标题、定理/定义/引理等
4. 产出 {output_path}，语义和符号不得改变

注意：你只处理这个 PDF 片段，不需要写 checkpoint，不需要续跑机制。
"""


def build_m0_prompt(paper_md_path: str, output_dir: str, handoff: dict = None) -> str:
    if handoff:
        pp = handoff.get("progress_pointer", {})
        return f"""这是模块 0 的续批处理。

上一批接力状态：
- 下一个流水号起点：{handoff.get('next_serial', '?')}
- 原始文件：{pp.get('file', 'paper.md')}
- 上一批处理到：{pp.get('after', '?')}（{pp.get('locator', {}).get('type', 'line')} {pp.get('locator', {}).get('value', '?')}）

请从上述位置之后继续处理，流水号从 {handoff.get('next_serial', '00001')} 开始。
已有产物在 {output_dir}/ 下，续写不覆盖。

处理前先加载 M0-01（工作流程）和 M0-02（MD+YAML），
然后从接力点继续逐篇处理。每完成一篇 md 的五步轮回后 Write {output_dir}/.checkpoint。
若 token 将耗尽，产出 {output_dir}/handoff_state.json 并停止。"""

    # 首轮 batch
    return f"""这是模块 0 的首轮处理。

输入文件：{paper_md_path}（由 Rewrite Agent 预处理的干净 markdown）
产物输出目录：{output_dir}/

## 执行步骤

1. 用 Read 工具读取 paper.md 全文
2. 加载以下 SKILL（调 Skill 工具）：
   - M0-01（工作流程：五步轮回 A→B→C→D→E）
   - M0-02（MD+YAML 产物规范）
   - M0-03（scope.json 规范）
   - M0-04（deps.json 规范）
   - M0-05（provenance.json 规范）
   - M0-06（index.json 规范）
3. 按 M0-01 的五步轮回，从文件开头逐篇处理：
   - Step 0: kind 预判（识别数学结构 → 选 kind；convention 走下方例外）
   - Step A: 写 md（逐字搬运正文 → 填 YAML → Write md）
   - Step B: 登记 index（label 非空 → Write global_name_index.json）
   - Step C: 追加 provenance（Write module0_provenance.json）
   - Step D: 构建依赖图 + 反查 scope.json 追加 affected_md（Write project_deps.json）
   - Step E: 写 checkpoint（Write .checkpoint）
   每篇 md 必须走完五步轮回才能开始下一篇。convention 跳过 Step A，直接写 scope.json → checkpoint。
4. 产物写入 {output_dir}/ 目录：
   - md 文件 → {output_dir}/md/<缩写>_<5位流水号>.md
   - global_name_index.json → {output_dir}/
   - module0_provenance.json → {output_dir}/
   - module0_scope.json → {output_dir}/
   - project_deps.json → {output_dir}/
5. 注意：paper.md 中的 [N] 格式引用为外部文献，记录为 external dangling（见 M0-04）
6. 全部处理完毕后，Write {output_dir}/handoff_state.json（含 next_serial 和 max_serial）
   若 token 将耗尽，Write {output_dir}/handoff_state.json（含 next_serial 和 progress_pointer）后停止。

宪法已通过系统提示注入，请严格遵守铁律和红线自查指令。"""


# ═══════════════════════════════════════════════════════════════
# KW Agent：单次调用，不分批
# ═══════════════════════════════════════════════════════════════

async def run_kw_agent(dp: DocPaths):
    constitution = (PROJECT_ROOT / "constitutions" / "KW-00.md").read_text(encoding="utf-8")

    opts = ClaudeAgentOptions(
        system_prompt=constitution,
        setting_sources=["project"],
        allowed_tools=["Read", "Write", "Skill"],
        skills=["KW-01", "KW-RF-source"],
        permission_mode="acceptEdits",
        cwd=str(PROJECT_ROOT),
        env=get_env(),
    )

    prompt = build_kw_prompt(str(dp.paper_md), str(dp.source_json))

    print(f"\n{'='*60}")
    print(f"🔑 KW Agent 启动")
    print(f"📄 输入: {dp.paper_md}")
    print(f"📝 输出: {dp.source_json}")
    print(f"{'='*60}\n")

    async for message in query(prompt=prompt, options=opts):
        msg_type = type(message).__name__
        if msg_type == "AssistantMessage":
            for block in getattr(message, "content", []):
                btype = type(block).__name__
                if btype == "TextBlock":
                    print(f"  💬 {block.text[:200]}", flush=True)
                elif btype == "ToolUseBlock":
                    print(f"  🔧 {block.name}({json.dumps(block.input, ensure_ascii=False)[:120]})", flush=True)
        elif msg_type == "ResultMessage":
            if message.is_error:
                raise RuntimeError(f"KW Agent 失败: {message.result}")
            print(f"  ✅ KW Agent 完成  turns={message.num_turns}  duration={message.duration_ms}ms")
            break


# ═══════════════════════════════════════════════════════════════
# Rewrite Agent：PDF 分块并发 + merge
# ═══════════════════════════════════════════════════════════════

async def _run_rw_one(pdf_path: str, md_path: str, constitution: str, label: str) -> str:
    """运行一个 RW Agent 处理单个 chunk PDF → md。返回 md_text。"""
    opts = ClaudeAgentOptions(
        system_prompt=constitution,
        setting_sources=["project"],
        allowed_tools=["Read", "Write", "Skill"],
        skills=["RW-01", "RW-RF-paper"],
        permission_mode="acceptEdits",
        cwd=str(PROJECT_ROOT),
        env=get_env_rw(),
        thinking={"type": "enabled", "budget_tokens": 16000},
        effort="max",
    )

    prompt = build_rw_prompt(pdf_path, md_path)
    async for message in query(prompt=prompt, options=opts):
        msg_type = type(message).__name__
        if msg_type == "ResultMessage":
            if message.is_error:
                raise RuntimeError(f"RW Agent [{label}] 失败: {message.result}")
            print(f"  ✅ RW [{label}] 完成  turns={message.num_turns}  duration={message.duration_ms}ms")
            return Path(md_path).read_text(encoding="utf-8")


async def run_rewrite_agent(dp: DocPaths):
    """并发处理 PDF 分块 → merge 为 paper.md。"""
    from frontend.fetch_papers import split_pdf

    if not os.environ.get("RW_ANTHROPIC_AUTH_TOKEN"):
        raise RuntimeError("RW_ANTHROPIC_AUTH_TOKEN 未设置，请在 .env 中配置火山 API Key")

    constitution = (PROJECT_ROOT / "constitutions" / "RW-00.md").read_text(encoding="utf-8")
    chunks = split_pdf(dp.pdf)

    if len(chunks) == 1:
        # 短论文：不分块，直接处理
        print(f"\n{'='*60}")
        print(f"📝 Rewrite Agent（单块，{chunks[0]}）")
        print(f"{'='*60}\n")
        await _run_rw_one(str(chunks[0]), str(dp.paper_md), constitution, "1/1")
        return

    # 长论文：分块并发
    chunk_dir = dp.paper_dir / "chunks"
    tasks = []
    for i, chunk_pdf in enumerate(chunks):
        chunk_md = chunk_dir / f"chunk_{i:04d}.md"
        print(f"  📋 调度 chunk {i+1}/{len(chunks)}: {chunk_pdf.name}")
        task = _run_rw_one(str(chunk_pdf), str(chunk_md), constitution, f"{i+1}/{len(chunks)}")
        tasks.append(task)

    print(f"\n{'='*60}")
    print(f"📝 Rewrite Agent（{len(chunks)} 块并发）")
    print(f"{'='*60}\n")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 检查失败 chunk，重试一次
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"  ⚠️ chunk {i+1}/{len(chunks)} 失败: {r}，重试...")
            chunk_md = chunk_dir / f"chunk_{i:04d}.md"
            try:
                results[i] = await _run_rw_one(str(chunks[i]), str(chunk_md),
                                               constitution, f"{i+1}/{len(chunks)} retry")
            except Exception as retry_err:
                raise RuntimeError(
                    f"RW chunk {i+1}/{len(chunks)} 重试仍失败: {retry_err}"
                ) from retry_err

    # 按顺序拼接 chunk md → paper.md（无重叠，直接拼接）
    print(f"\n  🔗 拼接 {len(chunks)} 个 chunk → paper.md")
    merged = []
    for i, chunk_pdf in enumerate(chunks):
        chunk_md = chunk_dir / f"chunk_{i:04d}.md"
        if chunk_md.exists():
            merged.append(chunk_md.read_text(encoding="utf-8"))
    dp.paper_md.write_text("\n".join(merged).strip() + "\n", encoding="utf-8")
    print(f"  📄 paper.md: {sum(m.count(chr(10)) for m in merged) + len(merged)} 行")

    # 清理 chunk 文件
    shutil.rmtree(chunk_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# M0 Agent：含分批接力逻辑
# ═══════════════════════════════════════════════════════════════

async def run_m0_agent(dp: DocPaths):
    constitution = (PROJECT_ROOT / "constitutions" / "M0-00.md").read_text(encoding="utf-8")

    opts = ClaudeAgentOptions(
        system_prompt=constitution,
        setting_sources=["project"],
        allowed_tools=["Read", "Write", "Bash", "Skill"],
        skills=M0_SKILLS,
        permission_mode="acceptEdits",
        cwd=str(PROJECT_ROOT),
        env=get_env(),
    )

    handoff = None
    batch_num = 0
    threshold_tokens = MODEL_CONTEXT_LIMIT * TOKEN_THRESHOLD

    while True:
        batch_num += 1
        # 记录 batch 前的 md 数量，用于判断是否有实质产出
        md_before = len(list(dp.md_dir.glob("*.md")))

        prompt = build_m0_prompt(str(dp.paper_md), str(dp.output_dir), handoff)

        if dp.checkpoint.exists():
            dp.checkpoint.unlink()

        input_tokens_seen = 0
        output_tokens_seen = 0
        over_threshold = False
        last_cp_mtime = 0.0
        cp_mtime_at_threshold = 0.0
        stopped_early = False

        print(f"\n{'='*60}")
        print(f"📦 M0 Batch {batch_num}")
        print(f"📂 输出: {dp.output_dir}")
        if handoff:
            print(f"🔁 续批: serial 从 {handoff['next_serial']} 起")
        print(f"🎯 分批阈值: {threshold_tokens:,.0f} tokens")
        print(f"{'='*60}\n")

        async for message in query(prompt=prompt, options=opts):
            msg_type = type(message).__name__

            if msg_type == "UserMessage":
                if hasattr(message, "usage") and message.usage:
                    input_tokens_seen = max(input_tokens_seen,
                                            _usage_val(message.usage, "input_tokens"))

            elif msg_type == "AssistantMessage":
                # 注：AssistantMessage 的 output_tokens 是本 turn 的增量，因此累加（+=）
                usage = message.usage or {}
                output_tokens_seen += _usage_val(usage, "output_tokens")
                for block in getattr(message, "content", []):
                    btype = type(block).__name__
                    if btype == "TextBlock":
                        text = block.text[:150]
                        print(f"  💬 {text}{'...' if len(block.text) > 150 else ''}", flush=True)
                    elif btype == "ToolUseBlock":
                        print(f"  🔧 {block.name}({json.dumps(block.input, ensure_ascii=False)[:120]})", flush=True)

            elif msg_type == "StreamEvent":
                # 注：StreamEvent 携带的是累计值而非增量，因此用 max 而非 +=
                inp, out = _usage_from_event(getattr(message, "event", {}))
                if inp:
                    input_tokens_seen = max(input_tokens_seen, inp)
                if out:
                    output_tokens_seen = max(output_tokens_seen, out)

            elif msg_type == "ResultMessage":
                if message.usage:
                    input_tokens_seen = _usage_val(message.usage, "input_tokens")
                    output_tokens_seen = _usage_val(message.usage, "output_tokens")
                print(f"\n  🏁 ResultMessage  turns={message.num_turns}  "
                      f"input={input_tokens_seen:,}  output={output_tokens_seen:,}")
                break

            # checkpoint 追踪
            if dp.checkpoint.exists():
                cp_mtime = dp.checkpoint.stat().st_mtime
                if cp_mtime > last_cp_mtime:
                    last_cp_mtime = cp_mtime
                    cp_content = dp.checkpoint.read_text(encoding="utf-8").strip()
                    total = input_tokens_seen + output_tokens_seen
                    print(f"  ✅ checkpoint: {cp_content}  tokens={total:,}", flush=True)

            # 阈值检测
            total_tokens = input_tokens_seen + output_tokens_seen
            if not over_threshold and total_tokens > threshold_tokens:
                over_threshold = True
                cp_mtime_at_threshold = last_cp_mtime
                print(f"\n  ⚠️ token 超阈值: {total_tokens:,} > {threshold_tokens:,.0f}  "
                      f"| 等待下一个 checkpoint...", flush=True)

            # 安全中断
            if over_threshold and dp.checkpoint.exists():
                cp_mtime = dp.checkpoint.stat().st_mtime
                if cp_mtime > cp_mtime_at_threshold:
                    print(f"  🛑 超阈值且 checkpoint 已更新 → 安全中断", flush=True)
                    stopped_early = True
                    break

        # 判断是否继续 —— 以 md 增量为主判据（不依赖 agent 的 state 字符串）
        md_after = len(list(dp.md_dir.glob("*.md")))
        no_progress = (md_after == md_before)

        if dp.handoff.exists():
            handoff_data = json.loads(dp.handoff.read_text(encoding="utf-8"))

            # 主判据：文件计数增量，不依赖 LLM 字符串
            # handoff_data["state"] 字段仅供人类阅读日志，agent 可能写 "complete"/
            # "completed"/"finished" 等变体——代码一律不读，靠 no_progress 做判断
            if no_progress:
                print(f"  ✅ 无新增 md（{md_before}→{md_after}），处理完成")
                break

            # 有增量，检查是否需要续跑
            if "next_serial" in handoff_data:
                handoff = handoff_data
                print(f"  🔁 新增 {md_after - md_before} 条 md，续批 serial={handoff['next_serial']}")
            else:
                break

        elif stopped_early and dp.checkpoint.exists():
            if no_progress:
                print(f"  ✅ 无新增 md，处理完成")
                break
            handoff = build_handoff_from_checkpoint(dp)
            if handoff is None:
                print(f"  ❌ 无法构造 handoff，终止")
                break
            print(f"  🔧 自构造 handoff: next_serial={handoff['next_serial']}")
        else:
            break


# ═══════════════════════════════════════════════════════════════
# 后处理
# ═══════════════════════════════════════════════════════════════

def backfill_forward_refs(dp: DocPaths):
    """Forward ref 回填 + 清理 handoff 文件。"""
    if not dp.deps.exists() or not dp.index.exists():
        return

    index = json.loads(dp.index.read_text(encoding="utf-8"))
    deps = json.loads(dp.deps.read_text(encoding="utf-8"))

    resolved_count = 0
    for node_id, node in deps.items():
        danglings = node.get("dangling", [])
        if not danglings:
            continue
        resolved = []
        for d in danglings:
            # 容错：agent 可能写 "Forward"/"FWD" 等变体，统一 lowercase
            dtype = d.get("type", "").lower()
            if dtype != "forward":
                continue
            ref = d.get("ref", "")
            if ref and ref in index:
                target_id = index[ref]
                # 容错：agent 可能写 "Statement"，统一 lowercase；缺失时默认 statement
                section = d.get("section", "").lower()
                if not section:
                    section = "statement"
                if section == "statement":
                    node.setdefault("statement_deps", []).append(target_id)
                else:
                    node.setdefault("proof_refs", []).append(target_id)
                resolved.append(d)
                resolved_count += 1
        for d in resolved:
            node["dangling"].remove(d)

    if resolved_count:
        dp.deps.write_text(
            json.dumps(deps, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  📝 回填 {resolved_count} 条 forward 引用")

    if dp.handoff.exists():
        dp.handoff.unlink()


# ═══════════════════════════════════════════════════════════════
# 单篇论文处理
# ═══════════════════════════════════════════════════════════════

async def process_paper(arxiv_id: str) -> bool:
    paper_dir = DATA_DIR / arxiv_id
    dp = DocPaths(paper_dir)

    if not dp.pdf.exists():
        print(f"  ⚠️ {arxiv_id}: paper.pdf 不存在，跳过")
        return False

    if not dp.source_json.exists():
        print(f"  ⚠️ {arxiv_id}: source.json 不存在，跳过")
        return False

    print(f"\n{'#'*60}")
    print(f"# 📄 开始处理: {arxiv_id}")
    print(f"{'#'*60}")

    try:
        # Step 2: Rewrite Agent（多模态 PDF → paper.md）
        await run_rewrite_agent(dp)

        # Step 3: KW Agent（读 paper.md → 填 ai_keywords）
        await run_kw_agent(dp)

        # Step 4: M0 Agent（读 paper.md → 结构化 md）
        dp.output_dir.mkdir(parents=True, exist_ok=True)
        dp.md_dir.mkdir(exist_ok=True)
        await run_m0_agent(dp)

        # 后处理
        try:
            backfill_forward_refs(dp)
        except Exception as bf_err:
            print(f"  ⚠️ backfill_forward_refs 失败: {bf_err}（M0 产物保留）")

        print(f"\n✅ {arxiv_id} 处理完成")
        return True

    except Exception as e:
        print(f"\n❌ {arxiv_id} 失败: {e}")
        shutil.rmtree(dp.output_dir, ignore_errors=True)   # 清理半成品
        if dp.paper_md.exists():
            dp.paper_md.unlink()
        shutil.rmtree(dp.paper_dir / "chunks", ignore_errors=True)  # 清理 chunk 缓存
        return False


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

async def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python orchestrator.py <arxiv_id> [<arxiv_id> ...]")
        print("  python orchestrator.py --all          # 处理 papers/ 下所有论文")
        sys.exit(1)

    if sys.argv[1] == "--all":
        paper_ids = sorted(
            d.name for d in DATA_DIR.iterdir()
            if d.is_dir() and (d / "paper.pdf").exists() and (d / "source.json").exists()
        )
        if not paper_ids:
            print("❌ 没有找到待处理的论文")
            sys.exit(1)
    else:
        paper_ids = sys.argv[1:]

    print(f"\n📋 待处理: {len(paper_ids)} 篇论文")
    for pid in paper_ids:
        print(f"  • {pid}")

    for arxiv_id in paper_ids:
        await process_paper(arxiv_id)

    print(f"\n{'='*60}")
    print(f"🏁 全部完成 — {len(paper_ids)} 篇论文处理完毕")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
