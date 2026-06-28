"""
Benchmark Make 服务：claude-agent-sdk 调 DeepSeek V4 Pro，按 SKILL 生成英文 .tex

架构（隔离沙箱 + 文件驱动，避免注意力稀释 & 跨 session 泄漏）：
  用户 6 字段 → 创建隔离沙箱 → 沙箱内只有 input.md + SKILL
  → 模型 CWD = 沙箱（看不到别的 session）→ 读 input.md + SKILL
  → 写 output.tex → 后端读出存 DB → 删除沙箱 → 前端下载
"""

import asyncio
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from .auth import get_current_user
from .database import get_db, now_iso

logger = logging.getLogger("benchmark")
router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])
_generating: dict[int, bool] = {}


class SessionSaveRequest(BaseModel):
    problem: str = ""
    origin: str = ""
    solution: str = ""
    rubric: str = ""
    doubao_answer: str = ""
    doubao_analysis: str = ""


# ─── DeepSeek 硬编码配置 ──────────────────────────────────

DEEPSEEK_ENV = {
    "ANTHROPIC_AUTH_TOKEN": "<DEEPSEEK_API_KEY>",
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
    "CLAUDE_CODE_STREAM_CLOSE_TIMEOUT": "3600000",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_SOURCE = PROJECT_ROOT / ".claude" / "skills" / "benchmark"
SANDBOX_BASE = PROJECT_ROOT / "server" / "benchmark_sandbox"


# ═══════════════════════════════════════════════════════════
#  隔离沙箱：每次生成创建独立工作区，模型只能看到当前 session
# ═══════════════════════════════════════════════════════════

def _build_input_md(fields: dict) -> str:
    """将 6 个字段拼接为结构化 Markdown"""
    return f"""# Benchmark Evaluation Input

## 1. Problem

{fields['problem']}

## 2. Origin of the Problem

{fields['origin']}

## 3. Solution to Problem

This solution was given by ChatGPT 5.5. Use EXACTLY this model name in the output.

{fields['solution']}

## 4. Rubric (Scoring Criteria)

{fields['rubric']}

## 5. Doubao Model's Answer

{fields['doubao_answer']}

## 6. Analysis of Doubao's Answer

{fields['doubao_analysis']}

---

**Processing Instructions:**
- Translate all Chinese content to English.
- VERBATIM TRANSLATE the Solution (Section 3) and Doubao's Answer (Section 5).
- Do NOT fabricate model names, versions, or dates. Use exactly what is provided above.
"""


def _create_sandbox(session_id: int, fields: dict) -> Path:
    """
    创建隔离沙箱。目录结构：
      sandbox_root/
        input.md                            ← 当前用户数据（唯一的 md 文件）
        output.tex                          ← 模型将写到这里
        .claude/skills/benchmark/SKILL.md   ← 从项目复制
        .claude/skills/benchmark/references/← 从项目复制

    模型 CWD = sandbox_root，别的 session 的文件不在这棵树里。
    """
    run_id = uuid.uuid4().hex[:8]
    sandbox = SANDBOX_BASE / f"run_{session_id}_{run_id}"

    # 如果有残留则清除
    if sandbox.exists():
        shutil.rmtree(sandbox, ignore_errors=True)
    sandbox.mkdir(parents=True)

    # 1) 写入 input.md
    (sandbox / "input.md").write_text(
        _build_input_md(fields), encoding="utf-8"
    )

    # 2) 复制 SKILL 文件（小文件，< 20KB，复制无性能问题）
    skill_dst = sandbox / ".claude" / "skills" / "benchmark"
    shutil.copytree(str(SKILL_SOURCE), str(skill_dst))

    logger.info(f"session={session_id} sandbox created: {sandbox}")
    return sandbox


def _destroy_sandbox(sandbox: Path):
    """生成结束后删除沙箱"""
    try:
        shutil.rmtree(sandbox, ignore_errors=True)
        logger.info(f"sandbox destroyed: {sandbox}")
    except Exception as e:
        logger.warning(f"sandbox cleanup failed ({sandbox}): {e}")


# ═══════════════════════════════════════════════════════════
#  提示词（极简 — 路径固定为 input.md / output.tex，无歧义）
# ═══════════════════════════════════════════════════════════

SYSTEM_PROMPT = (
    "You are a LaTeX benchmark document compiler.\n\n"
    "Workflow:\n"
    "1. Read the benchmark input file at: input.md\n"
    "2. Load the benchmark SKILL (use the Skill tool) and read "
    "its references/template-structure.md for the full structural spec.\n"
    "3. Process all 6 input sections according to the SKILL rules.\n"
    "4. Write the complete .tex output to: output.tex\n\n"
    "Critical constraints:\n"
    "- The .tex must start with \\documentclass{article} and end "
    "with \\end{document}.\n"
    "- Follow the SKILL's document structure, numbering, and "
    "formatting exactly.\n"
    "- VERBATIM TRANSLATE the Solution and Doubao's Answer sections.\n"
    "- Output ONLY the .tex file via the Write tool. "
    "No commentary, no summary, no extra files.\n"
    "- Your working directory contains ONLY input.md. "
    "Do NOT look for or read any other input files."
)

USER_PROMPT = (
    "Read the benchmark input from `input.md`, "
    "follow the benchmark SKILL, "
    "and write the complete .tex document to `output.tex`."
)


# ═══════════════════════════════════════════════════════════
#  后台生成任务
# ═══════════════════════════════════════════════════════════

async def _generate_tex(session_id: int, fields: dict):
    tex_content = ""
    sandbox = None

    # 标记为 running
    db = get_db()
    try:
        db.execute(
            "INSERT OR REPLACE INTO benchmark_outputs "
            "(session_id, status, generated_at) VALUES (?, 'running', ?)",
            (session_id, now_iso()),
        )
        db.commit()
    finally:
        db.close()

    try:
        # ── 1. 创建隔离沙箱 ─────────────────────────────
        sandbox = _create_sandbox(session_id, fields)
        output_path = sandbox / "output.tex"

        # ── 2. 调用 claude-agent-sdk ─────────────────────
        from claude_agent_sdk import query
        from claude_agent_sdk.types import ClaudeAgentOptions

        opts = ClaudeAgentOptions(
            cwd=str(sandbox),               # ★ CWD = 沙箱，不是项目根
            setting_sources=["project"],
            skills="all",
            allowed_tools=["Skill", "Read", "Write"],
            permission_mode="bypassPermissions",
            env=DEEPSEEK_ENV,
            system_prompt=SYSTEM_PROMPT,
            model="deepseek-v4-pro",
            include_partial_messages=True,
            load_timeout_ms=3600000,
        )

        last_text = ""
        final_result = ""

        try:
            async for message in query(prompt=USER_PROMPT, options=opts):
                name = type(message).__name__
                if name == "AssistantMessage":
                    for block in getattr(message, "content", []):
                        btype = type(block).__name__
                        if btype == "TextBlock":
                            text = block.text or ""
                            if text:
                                last_text = text
                elif name == "ResultMessage":
                    if (
                        not getattr(message, "is_error", True)
                        and getattr(message, "result", "")
                    ):
                        final_result = message.result
        except Exception as stream_err:
            logger.warning(
                f"session={session_id} stream interrupted: {stream_err}"
            )
            if not last_text and not final_result and not output_path.exists():
                raise

        # ── 3. 读取 tex（优先文件，回退响应文本）──────────
        if output_path.exists():
            tex_content = output_path.read_text(encoding="utf-8").strip()
            logger.info(
                f"session={session_id} read tex from sandbox file "
                f"({len(tex_content)} chars)"
            )
        else:
            logger.warning(
                f"session={session_id} output.tex not found in sandbox, "
                f"falling back to response text"
            )
            tex_content = final_result or last_text

        # ── 4. 清理内容 ─────────────────────────────────
        tex_content = tex_content.strip()

        # 清理 markdown 围栏
        if tex_content.startswith("```"):
            lines = tex_content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            tex_content = "\n".join(lines).strip()

        # 定位 \documentclass
        idx = tex_content.find("\\documentclass")
        if idx > 0:
            tex_content = tex_content[idx:]

        # 截断 \end{document} 之后的内容
        end_idx = tex_content.find("\\end{document}")
        if end_idx > 0:
            tex_content = tex_content[: end_idx + len("\\end{document}")]

        # ── 5. 保存到数据库 ──────────────────────────────
        db = get_db()
        try:
            db.execute(
                "UPDATE benchmark_outputs "
                "SET tex_content=?, status='done', generated_at=? "
                "WHERE session_id=?",
                (tex_content, now_iso(), session_id),
            )
            db.commit()
        finally:
            db.close()

    except Exception as e:
        logger.error(f"session={session_id} error: {e}")
        db = get_db()
        try:
            db.execute(
                "UPDATE benchmark_outputs "
                "SET status='error', tex_content=? WHERE session_id=?",
                (f"[Error] {e}", session_id),
            )
            db.commit()
        finally:
            db.close()
    finally:
        _generating.pop(session_id, None)
        # ── 6. 销毁沙箱 ─────────────────────────────────
        if sandbox:
            _destroy_sandbox(sandbox)


# ═══════════════════════════════════════════════════════════
#  API 端点（接口不变，前端无感）
# ═══════════════════════════════════════════════════════════

@router.post("/sessions")
def create_session(
    body: SessionSaveRequest, user: dict = Depends(get_current_user)
):
    db = get_db()
    try:
        now = now_iso()
        cur = db.execute(
            "INSERT INTO benchmark_sessions "
            "(user_id, problem, origin, solution, rubric, "
            "doubao_answer, doubao_analysis, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                user["user_id"],
                body.problem,
                body.origin,
                body.solution,
                body.rubric,
                body.doubao_answer,
                body.doubao_analysis,
                now,
                now,
            ),
        )
        db.commit()
        return {"session_id": cur.lastrowid}
    finally:
        db.close()


@router.put("/sessions/{session_id}")
def update_session(
    session_id: int,
    body: SessionSaveRequest,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    try:
        row = db.execute(
            "SELECT session_id FROM benchmark_sessions "
            "WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Session not found")
        db.execute(
            "UPDATE benchmark_sessions SET problem=?, origin=?, solution=?, "
            "rubric=?, doubao_answer=?, doubao_analysis=?, updated_at=? "
            "WHERE session_id=?",
            (
                body.problem,
                body.origin,
                body.solution,
                body.rubric,
                body.doubao_answer,
                body.doubao_analysis,
                now_iso(),
                session_id,
            ),
        )
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.get("/sessions")
def list_sessions(user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        rows = db.execute(
            "SELECT session_id, title, problem, created_at, updated_at, pinned "
            "FROM benchmark_sessions WHERE user_id=? AND hidden=0 "
            "ORDER BY pinned DESC, updated_at DESC LIMIT 50",
            (user["user_id"],),
        ).fetchall()
        return [
            {
                "session_id": r["session_id"],
                "title": r["title"] or (r["problem"] or "Untitled")[:60],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "pinned": bool(r["pinned"]),
                "generating": r["session_id"] in _generating,
            }
            for r in rows
        ]
    finally:
        db.close()


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int, user: dict = Depends(get_current_user)
):
    db = get_db()
    try:
        s = db.execute(
            "SELECT * FROM benchmark_sessions "
            "WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not s:
            raise HTTPException(404, "Session not found")
        output = db.execute(
            "SELECT tex_content, status, generated_at "
            "FROM benchmark_outputs WHERE session_id=?",
            (session_id,),
        ).fetchone()
        return {
            "session_id": s["session_id"],
            "title": s["title"] or (s["problem"] or "Untitled")[:60],
            "problem": s["problem"],
            "origin": s["origin"],
            "solution": s["solution"],
            "rubric": s["rubric"],
            "doubao_answer": s["doubao_answer"],
            "doubao_analysis": s["doubao_analysis"],
            "created_at": s["created_at"],
            "updated_at": s["updated_at"],
            "output": {
                "tex_content": output["tex_content"] if output else None,
                "status": output["status"] if output else None,
                "generated_at": output["generated_at"] if output else None,
            }
            if output
            else None,
            "generating": session_id in _generating,
        }
    finally:
        db.close()


@router.post("/sessions/{session_id}/generate")
async def generate_tex(
    session_id: int, user: dict = Depends(get_current_user)
):
    if session_id in _generating:
        raise HTTPException(409, "Already generating")
    db = get_db()
    try:
        s = db.execute(
            "SELECT * FROM benchmark_sessions "
            "WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not s:
            raise HTTPException(404, "Session not found")
        fields = {
            k: s[k]
            for k in [
                "problem",
                "origin",
                "solution",
                "rubric",
                "doubao_answer",
                "doubao_analysis",
            ]
        }
        empty = [k for k, v in fields.items() if not v or not v.strip()]
        if empty:
            raise HTTPException(400, f"Missing fields: {', '.join(empty)}")
    finally:
        db.close()
    _generating[session_id] = True
    asyncio.create_task(_generate_tex(session_id, fields))
    return {"ok": True, "status": "started"}


@router.get("/sessions/{session_id}/download")
def download_tex(
    session_id: int, user: dict = Depends(get_current_user)
):
    db = get_db()
    try:
        s = db.execute(
            "SELECT session_id FROM benchmark_sessions "
            "WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not s:
            raise HTTPException(404)
        output = db.execute(
            "SELECT tex_content, status "
            "FROM benchmark_outputs WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if not output or output["status"] != "done" or not output["tex_content"]:
            raise HTTPException(404, "No output available")
        return Response(
            content=output["tex_content"],
            media_type="application/x-tex",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=benchmark_{session_id}.tex"
                )
            },
        )
    finally:
        db.close()


@router.post("/sessions/{session_id}/rename")
def rename_session(
    session_id: int, body: dict, user: dict = Depends(get_current_user)
):
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "Title is required")
    db = get_db()
    try:
        row = db.execute(
            "SELECT session_id FROM benchmark_sessions "
            "WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404)
        db.execute(
            "UPDATE benchmark_sessions SET title=? WHERE session_id=?",
            (title, session_id),
        )
        db.commit()
        return {"ok": True, "title": title}
    finally:
        db.close()


@router.post("/sessions/{session_id}/pin")
def pin_session(
    session_id: int, user: dict = Depends(get_current_user)
):
    db = get_db()
    try:
        row = db.execute(
            "SELECT pinned FROM benchmark_sessions "
            "WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404)
        new = 0 if row["pinned"] else 1
        db.execute(
            "UPDATE benchmark_sessions SET pinned=? WHERE session_id=?",
            (new, session_id),
        )
        db.commit()
        return {"pinned": bool(new)}
    finally:
        db.close()


@router.post("/sessions/{session_id}/hide")
def hide_session(
    session_id: int, user: dict = Depends(get_current_user)
):
    db = get_db()
    try:
        db.execute(
            "UPDATE benchmark_sessions SET hidden=1 "
            "WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        )
        db.commit()
        return {"ok": True}
    finally:
        db.close()
