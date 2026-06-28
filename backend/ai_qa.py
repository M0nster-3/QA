"""
AI 多次独立回答服务（OpenAI SDK 版 + 续写模式）。

架构：
- 后台任务独立于 SSE 连接：即使客户端断开，agent 继续跑，结果存 DB
- SSE 只服务当前页面（不跨导航重连）
- 回来查 DB 获取已完成的答案，轮询等待未完成的

续写模式（修复版）：
- 截断检测：response.incomplete 事件（思考截断）
             + response.completed 中 finish_reason=="length"（回答截断）
- 续写方式：Responses API 的 previous_response_id（非 Chat 的 partial=True）
- 流管理：async with await create(...) as stream: 一步到位，防迭代器覆盖
- 任务引用：全局 set 持有 Task 强引用，防 GC 回收
"""

import asyncio
import json
import logging
import os
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .auth import get_current_user
from .database import get_db, now_iso

logger = logging.getLogger("ai_qa")
router = APIRouter(prefix="/api/ai", tags=["ai"])

# 全局：session_id → set of running slot numbers
_running: dict[int, set[int]] = {}
_running_lock = asyncio.Lock()

# ★ 修复根因 4：全局强引用集合，防止 asyncio Task 被 GC 回收
_background_tasks: set[asyncio.Task] = set()


class GenerateRequest(BaseModel):
    question: str
    count: int = 1


# ─── 硬编码配置 ───────────────────────────────────────────

BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
API_KEY = "<VOLC_ENGINE_API_KEY>"
MODEL = "doubao-seed-2-1-pro-260628"
MAX_OUTPUT_TOKENS = 262144
MAX_CONTINUATIONS = 20      # 续写上限，防止死循环
ARK_MAX_RPM = 500
ARK_RATE_WINDOW_SECONDS = 60.0
MAX_CONCURRENT_ARK_REQUESTS = 500
ARK_MAX_WAIT_TIMEOUT_MS = "300000"

_ark_request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ARK_REQUESTS)
_ark_request_started_at: deque[float] = deque()
_ark_rate_lock = asyncio.Lock()

CONTINUATION_PROMPT = (
    "Your previous response was truncated due to length limits. "
    "Continue exactly from where you left off. "
    "Do not repeat any content already generated. "
    "Do not add any preamble or summary of what came before."
)

EMPTY_ANSWER_PROMPT = (
    "Your previous response produced reasoning but no final answer text. "
    "Now provide the final answer to the original question. "
    "Do not include a preamble about the previous response."
)


def _get_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=3600.0)


async def _wait_for_ark_rpm_slot():
    """Keep local request starts within the public 500 RPM model limit."""
    while True:
        loop = asyncio.get_running_loop()
        async with _ark_rate_lock:
            now = loop.time()
            while (
                _ark_request_started_at
                and now - _ark_request_started_at[0] >= ARK_RATE_WINDOW_SECONDS
            ):
                _ark_request_started_at.popleft()

            if len(_ark_request_started_at) < ARK_MAX_RPM:
                _ark_request_started_at.append(now)
                return

            wait_seconds = (
                ARK_RATE_WINDOW_SECONDS - (now - _ark_request_started_at[0])
            )

        await asyncio.sleep(max(wait_seconds, 0.05))


def _get_text_attr(obj, *names: str) -> str:
    for name in names:
        value = getattr(obj, name, None)
        if isinstance(value, str) and value:
            return value
    return ""


async def _merge_aggregate_text(
    *,
    current: str,
    chunk_start: int,
    aggregate: str,
    queue: asyncio.Queue | None,
    queue_kind: str,
    slot: int,
    label: str,
) -> str:
    """
    方舟会发送 response.output_text.done / reasoning_summary_text.done 的聚合文本。
    delta 正常时它只作校验；delta 丢失或只收到一部分时，用 done 事件补齐。
    """
    if not aggregate:
        return current

    chunk = current[chunk_start:]
    if aggregate == chunk:
        return current

    if aggregate.startswith(chunk):
        suffix = aggregate[len(chunk):]
        if suffix:
            current += suffix
            if queue:
                await queue.put((queue_kind, slot, suffix))
        return current

    if not chunk:
        current += aggregate
        if queue:
            await queue.put((queue_kind, slot, aggregate))
        return current

    logger.warning(
        f"slot={slot} {label} aggregate differed from streamed delta; "
        f"using aggregate for DB save"
    )
    return current[:chunk_start] + aggregate


def _extract_completed_output_text(resp) -> str:
    """Best-effort fallback for response.completed when text done/delta was missed."""
    parts: list[str] = []

    for item in getattr(resp, "output", None) or []:
        text = _get_text_attr(item, "text", "output_text")
        if text:
            parts.append(text)

        for content in getattr(item, "content", None) or []:
            text = _get_text_attr(content, "text", "output_text")
            if text:
                parts.append(text)

    for choice in getattr(resp, "choices", None) or []:
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str) and content:
            parts.append(content)

    return "".join(parts)


# ─── Agent 调用（后台任务 + 续写循环）────────────────────

SYSTEM_PROMPT = ""


async def _run_agent(session_id: int, slot: int, question: str, queue: asyncio.Queue | None):
    """
    独立后台任务，支持续写模式。
    修复 4 个根因：
      1) async with await create(...) as stream — 防迭代器覆盖丢事件
      2) 双事件截断检测 — response.incomplete + finish_reason=="length"
      3) previous_response_id 续写 — 非 Chat 的 partial=True
      4) Task 强引用 — 由 _background_tasks 持有（见 _stream_slots）
    """
    thinking = ""
    answer = ""
    prev_response_id = None
    retry_empty_answer = False

    try:
        client = _get_client()

        for iteration in range(MAX_CONTINUATIONS):

            # ── 构建请求参数 ─────────────────────────────
            if iteration == 0:
                input_data = question
                extra_params = {}
            else:
                # ★ 修复根因 3：用 previous_response_id 续写，不用 partial=True
                input_data = EMPTY_ANSWER_PROMPT if retry_empty_answer else CONTINUATION_PROMPT
                extra_params = {"previous_response_id": prev_response_id}
                logger.info(
                    f"session={session_id} slot={slot} "
                    f"continuation {iteration}/{MAX_CONTINUATIONS} "
                    f"prev_response_id={prev_response_id} "
                    f"(thinking={len(thinking)}c, answer={len(answer)}c)"
                )
                if queue:
                    await queue.put(("continuation", slot, iteration))

            retry_empty_answer = False
            truncated = False
            current_response_id = None
            answer_start = len(answer)
            thinking_start = len(thinking)

            # ── 调用模型（流式）─────────────────────────
            # ★ 修复根因 1：async with await ... as stream: 一步到位
            #   不能先 stream = await create(...)，再 async with stream:
            #   否则 __aenter__ 重建迭代器，丢弃预读事件
            if queue:
                await queue.put(("queued", slot, None))

            async with _ark_request_semaphore:
                await _wait_for_ark_rpm_slot()
                if queue:
                    await queue.put(("started", slot, None))

                async with await client.responses.create(
                    model=MODEL,
                    instructions=SYSTEM_PROMPT,
                    input=input_data,
                    stream=True,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    extra_body={"thinking": {"type": "enabled"}},
                    reasoning={"effort": "high"},
                    extra_headers={"X-Ark-Max-Wait-Timeout-Ms": ARK_MAX_WAIT_TIMEOUT_MS},
                    **extra_params,
                ) as stream:
                    async for event in stream:
                        etype = getattr(event, "type", "")

                        # 捕获 response ID（用于下一轮续写）
                        if etype == "response.created":
                            resp = getattr(event, "response", None)
                            if resp:
                                current_response_id = getattr(resp, "id", None)

                        # 思考链 delta — 跨续写拼接
                        elif etype == "response.reasoning_summary_text.delta":
                            delta = event.delta or ""
                            thinking += delta
                            if queue:
                                await queue.put(("thinking", slot, delta))

                        elif etype == "response.reasoning_summary_text.done":
                            thinking = await _merge_aggregate_text(
                                current=thinking,
                                chunk_start=thinking_start,
                                aggregate=_get_text_attr(event, "text"),
                                queue=queue,
                                queue_kind="thinking",
                                slot=slot,
                                label="reasoning",
                            )

                        # 回答 delta — 跨续写无缝拼接
                        elif etype == "response.output_text.delta":
                            delta = event.delta or ""
                            answer += delta
                            if queue:
                                await queue.put(("answer", slot, delta))

                        elif etype == "response.output_text.done":
                            answer = await _merge_aggregate_text(
                                current=answer,
                                chunk_start=answer_start,
                                aggregate=_get_text_attr(event, "text"),
                                queue=queue,
                                queue_kind="answer",
                                slot=slot,
                                label="answer",
                            )

                        # ★ 修复根因 2a：思考截断 / 超时截断
                        #   火山方舟发 response.incomplete 事件（不发 completed）
                        elif etype == "response.incomplete":
                            truncated = True
                            resp = getattr(event, "response", None)
                            if resp:
                                current_response_id = (
                                    getattr(resp, "id", None) or current_response_id
                                )
                                reason = ""
                                details = getattr(resp, "incomplete_details", None)
                                if details:
                                    reason = getattr(details, "reason", "")
                                logger.info(
                                    f"session={session_id} slot={slot} "
                                    f"incomplete event (reason={reason}) "
                                    f"at iteration {iteration + 1}"
                                )

                        # ★ 修复根因 2b：回答长度截断
                        #   火山方舟发 response.completed，status=completed，
                        #   截断标记在 output/choices 的 finish_reason=="length"
                        elif etype == "response.completed":
                            resp = getattr(event, "response", None)
                            if resp:
                                current_response_id = (
                                    getattr(resp, "id", None) or current_response_id
                                )
                                completed_text = _extract_completed_output_text(resp)
                                answer = await _merge_aggregate_text(
                                    current=answer,
                                    chunk_start=answer_start,
                                    aggregate=completed_text,
                                    queue=queue,
                                    queue_kind="answer",
                                    slot=slot,
                                    label="completed answer",
                                )

                                # 兼容 output (Responses API) 和 choices (兼容格式)
                                items = (
                                    getattr(resp, "output", None)
                                    or getattr(resp, "choices", None)
                                    or []
                                )
                                for item in items:
                                    fr = getattr(item, "finish_reason", "")
                                    if fr == "length":
                                        truncated = True
                                        logger.info(
                                            f"session={session_id} slot={slot} "
                                            f"finish_reason=length "
                                            f"at iteration {iteration + 1}"
                                        )
                                # 兜底：也检查 status==incomplete
                                if getattr(resp, "status", "") == "incomplete":
                                    truncated = True

            # async with 退出：连接已安全归还到连接池

            # 更新 response ID 用于下一轮续写
            if current_response_id:
                prev_response_id = current_response_id

            if not answer.strip():
                if prev_response_id and iteration < MAX_CONTINUATIONS - 1:
                    truncated = True
                    retry_empty_answer = True
                    logger.warning(
                        f"session={session_id} slot={slot} "
                        f"got reasoning but empty answer at iteration {iteration + 1}; "
                        "retrying with previous_response_id"
                    )
                else:
                    raise RuntimeError("Empty answer after reasoning stream")

            # ── 未截断 → 完成 ────────────────────────────
            if not truncated:
                logger.info(
                    f"session={session_id} slot={slot} "
                    f"completed after {iteration + 1} iteration(s) "
                    f"(thinking={len(thinking)}c, answer={len(answer)}c)"
                )
                break

        else:
            # 达到最大续写次数
            logger.warning(
                f"session={session_id} slot={slot} "
                f"hit max continuations ({MAX_CONTINUATIONS})"
            )
            if queue:
                await queue.put(("max_cont", slot, MAX_CONTINUATIONS))

        _save_answer(session_id, slot, thinking, answer)
        if queue:
            await queue.put(("done", slot, None))

    except Exception as e:
        logger.error(f"session={session_id} slot={slot} error: {e}")
        _save_answer(session_id, slot, thinking, f"[Error] {e}")
        if queue:
            await queue.put(("error", slot, str(e)))

    finally:
        async with _running_lock:
            if session_id in _running:
                _running[session_id].discard(slot)
                if not _running[session_id]:
                    del _running[session_id]


def _save_answer(session_id: int, slot: int, thinking: str, answer: str):
    db = get_db()
    try:
        db.execute(
            "INSERT OR REPLACE INTO ai_answers "
            "(session_id, slot, thinking, answer, generated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, slot, thinking, answer, now_iso()),
        )
        db.commit()
    finally:
        db.close()


# ─── SSE 生成器 ─────────────────────────────────────────────

def _sse_line(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, 'data': data}, ensure_ascii=False)}\n\n"


async def _stream_slots(question: str, count: int, session_id: int, slots_to_run: list[int]):
    """通用 SSE 生成器。为指定的 slot 列表启动 agent 并流式输出。"""
    queue: asyncio.Queue = asyncio.Queue()
    done_count = 0
    total = len(slots_to_run)

    async with _running_lock:
        if session_id not in _running:
            _running[session_id] = set()
        for slot in slots_to_run:
            _running[session_id].add(slot)

    # ★ 修复根因 4：Task 加入全局 set 强引用，防止 GC 回收
    for slot in slots_to_run:
        task = asyncio.create_task(_run_agent(session_id, slot, question, queue))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    yield _sse_line("session", {"session_id": session_id})

    try:
        while done_count < total:
            kind, slot, payload = await queue.get()

            if kind == "thinking":
                yield _sse_line(f"slot_{slot}_thinking", {"token": payload})
            elif kind == "answer":
                yield _sse_line(f"slot_{slot}_answer", {"token": payload})
            elif kind == "queued":
                yield _sse_line(f"slot_{slot}_queued", {})
            elif kind == "started":
                yield _sse_line(f"slot_{slot}_started", {})
            elif kind == "done":
                done_count += 1
                yield _sse_line(f"slot_{slot}_done", {})
            elif kind == "error":
                done_count += 1
                yield _sse_line(f"slot_{slot}_error", {"error": payload})
            elif kind == "continuation":
                yield _sse_line(f"slot_{slot}_continuation", {"iteration": payload})
            elif kind == "max_cont":
                yield _sse_line(f"slot_{slot}_max_cont", {"max": payload})

    except asyncio.CancelledError:
        pass


# ─── API 端点 ────────────────────────────────────────────────

@router.post("/generate")
async def generate(body: GenerateRequest, user: dict = Depends(get_current_user)):
    if not 1 <= body.count <= 8:
        raise HTTPException(400, "count must be 1-8")

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO ai_sessions (user_id, question, answer_count, created_at) VALUES (?,?,?,?)",
            (user["user_id"], body.question, body.count, now_iso()),
        )
        db.commit()
        session_id = cur.lastrowid
    finally:
        db.close()

    return StreamingResponse(
        _stream_slots(body.question, body.count, session_id, list(range(1, body.count + 1))),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/regenerate/{slot}")
async def regenerate(session_id: int, slot: int, user: dict = Depends(get_current_user)):
    if not 1 <= slot <= 8:
        raise HTTPException(400, "slot must be 1-8")

    db = get_db()
    try:
        row = db.execute(
            "SELECT question FROM ai_sessions WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Session not found")
        question = row["question"]
    finally:
        db.close()

    return StreamingResponse(
        _stream_slots(question, 1, session_id, [slot]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions")
def list_sessions(user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        rows = db.execute(
            "SELECT session_id, question, answer_count, created_at, pinned "
            "FROM ai_sessions WHERE user_id=? AND hidden=0 "
            "ORDER BY pinned DESC, created_at DESC LIMIT 50",
            (user["user_id"],),
        ).fetchall()
        return [
            {
                "session_id": r["session_id"],
                "question": r["question"],
                "answer_count": r["answer_count"],
                "created_at": r["created_at"],
                "pinned": bool(r["pinned"]),
                "running": r["session_id"] in _running,
            }
            for r in rows
        ]
    finally:
        db.close()


@router.get("/sessions/{session_id}")
def session_detail(session_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        s = db.execute(
            "SELECT * FROM ai_sessions WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not s:
            raise HTTPException(404, "Session not found")

        answers = db.execute(
            "SELECT slot, thinking, answer, generated_at "
            "FROM ai_answers WHERE session_id=? ORDER BY slot",
            (session_id,),
        ).fetchall()

        running_slots = sorted(_running.get(session_id, set()))

        return {
            "session_id": s["session_id"],
            "question": s["question"],
            "answer_count": s["answer_count"],
            "created_at": s["created_at"],
            "running": len(running_slots) > 0,
            "running_slots": running_slots,
            "answers": [
                {
                    "slot": r["slot"],
                    "thinking": r["thinking"],
                    "answer": r["answer"],
                    "generated_at": r["generated_at"],
                }
                for r in answers
            ],
        }
    finally:
        db.close()


@router.post("/sessions/{session_id}/pin")
def pin_session(session_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        row = db.execute(
            "SELECT pinned FROM ai_sessions WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404)
        new = 0 if row["pinned"] else 1
        db.execute("UPDATE ai_sessions SET pinned=? WHERE session_id=?", (new, session_id))
        db.commit()
        return {"pinned": bool(new)}
    finally:
        db.close()


@router.post("/sessions/{session_id}/hide")
def hide_session(session_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        db.execute(
            "UPDATE ai_sessions SET hidden=1 WHERE session_id=? AND user_id=?",
            (session_id, user["user_id"]),
        )
        db.commit()
        return {"ok": True}
    finally:
        db.close()
