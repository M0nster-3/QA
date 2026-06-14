"""
并发分发器 · dispatcher.py

读 _batch_index.json，按断点续传方式并发现有管线处理每篇论文。
asyncio + Semaphore 控制并发，arxiv 下载遵守 3 秒间隔。

用法:
  python frontend/dispatcher.py                           # 默认 20 并发
  python frontend/dispatcher.py --concurrency 50          # 50 并发
  python frontend/dispatcher.py --concurrency 10 --start 0 --end 100
  python frontend/dispatcher.py --dry-run                 # 只打印配置信息
"""

import os, sys, json, time, asyncio, shutil
from pathlib import Path

# ── 自动加载项目 .env（跨模型配置：DS + 火山多模态）──
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

# ── 确保项目根在 sys.path ──────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.fetch_papers import download_paper, create_source_json
from frontend.orchestrator import process_paper, DATA_DIR

# ── 默认路径 ───────────────────────────────────────────────
DEFAULT_INDEX = DATA_DIR / "_batch_index.json"
DEFAULT_STATE = DATA_DIR / "_batch_state.json"

ARXIV_DOWNLOAD_INTERVAL = 3.0  # arxiv 要求的请求间隔


# ═══════════════════════════════════════════════════════════════
# 断点状态
# ═══════════════════════════════════════════════════════════════

def load_state() -> dict:
    """加载断点状态。"""
    if DEFAULT_STATE.exists():
        state = json.loads(DEFAULT_STATE.read_text(encoding="utf-8"))
        state.setdefault("ahead", [])
        return state
    return {"total": 0, "next_index": 0, "ahead": [], "completed": 0, "failed": {}, "updated_at": ""}


def save_state(state: dict):
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    DEFAULT_STATE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ═══════════════════════════════════════════════════════════════
# 单篇处理
# ═══════════════════════════════════════════════════════════════

async def process_one(
    paper: dict,
    index: int,
    sem: asyncio.Semaphore,
    download_lock: asyncio.Lock,
    last_download_time: list[float],
):
    """处理一篇论文：下载 + 管道。下载遵守 arxiv 3 秒间隔。"""
    arxiv_id = paper["arxiv_id"]
    paper_dir = DATA_DIR / arxiv_id

    async with sem:
        # ── Step 1: 创建 source.json ──
        source_path = paper_dir / "source.json"
        if not source_path.exists():
            await asyncio.to_thread(create_source_json, paper)

        # ── Step 2: 下载 PDF（串行，遵守 3 秒间隔） ──
        pdf_path = paper_dir / "paper.pdf"
        if not pdf_path.exists():
            async with download_lock:
                # 再检一次（等锁期间可能已被另一任务下载）
                if not pdf_path.exists():
                    elapsed = time.time() - last_download_time[0]
                    if elapsed < ARXIV_DOWNLOAD_INTERVAL:
                        await asyncio.sleep(ARXIV_DOWNLOAD_INTERVAL - elapsed)
                    ok = await asyncio.to_thread(download_paper, arxiv_id)
                    last_download_time[0] = time.time()
                    if not ok:
                        raise RuntimeError(f"下载失败: {arxiv_id}")

        # ── Step 3: 管道处理（RW → KW → M0） ──
        ok = await process_paper(arxiv_id)
        if not ok:
            raise RuntimeError(f"管道处理失败: {arxiv_id}")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="并发分发器 · 批量管道处理")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="元数据索引 JSON 路径")
    parser.add_argument("--state", default=str(DEFAULT_STATE), help="断点状态文件路径")
    parser.add_argument("--concurrency", type=int, default=20, help="并发数 (默认 20)")
    parser.add_argument("--start", type=int, default=None, help="起始索引 (覆盖断点)")
    parser.add_argument("--end", type=int, default=None, help="结束索引 (不含)")
    parser.add_argument("--dry-run", action="store_true", help="只打印配置，不处理")
    args = parser.parse_args()

    # 加载索引
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"❌ 索引文件不存在: {index_path}")
        print(f"   请先运行: python tools/batch_index.py")
        sys.exit(1)

    all_papers = json.loads(index_path.read_text(encoding="utf-8"))
    total = len(all_papers)
    print(f"📂 索引: {total} 篇论文 ({index_path})")

    # 加载/覆盖断点
    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    state.setdefault("total", total)
    state.setdefault("ahead", [])
    state.setdefault("next_index", 0)
    state.setdefault("completed", 0)
    state.setdefault("failed", {})

    start_idx = args.start if args.start is not None else state["next_index"]
    end_idx = args.end if args.end is not None else total
    papers = all_papers[start_idx:end_idx]

    print(f"⚡ 并发数: {args.concurrency}")
    print(f"📍 范围: [{start_idx}, {end_idx}) ({len(papers)} 篇)")
    print(f"📊 已完成: {state['completed']}, 失败: {len(state['failed'])}")

    if args.dry_run:
        print(f"\n📋 前 5 篇:")
        for p in papers[:5]:
            print(f"  {p['arxiv_id']} — {p.get('title', '?')[:70]}...")
        return

    if not papers:
        print("✅ 全部完成，无待处理论文")
        state_path.unlink(missing_ok=True)
        return

    # 更新状态
    state["total"] = total
    state["next_index"] = start_idx
    save_state(state)

    # ── 并发处理 ────────────────────────────────────────
    sem = asyncio.Semaphore(args.concurrency)
    download_lock = asyncio.Lock()
    last_download_time = [0.0]  # 可变引用，共享下载计时
    state_lock = asyncio.Lock()  # 保护 state 写入

    print(f"\n{'='*60}")
    print(f"🚀 开始处理 (并发={args.concurrency})")
    print(f"{'='*60}\n")

    start_time = time.time()
    completed_this_run = 0
    failed_this_run = 0

    def _advance_watermark():
        """推进低水位线：连续完成/失败则前进，遇到缺口停住。调用方需持有 state_lock。"""
        nxt = state["next_index"]
        ahead = set(state.get("ahead", []))
        while nxt in ahead or str(nxt) in state.get("failed", {}):
            if nxt in ahead:
                ahead.discard(nxt)
            nxt += 1
        state["next_index"] = nxt
        state["ahead"] = sorted(ahead)
        save_state(state)

    async def process_one_with_state(paper: dict, global_idx: int):
        """包装 process_one，处理异常 + 更新状态（低水位线算法）。"""
        nonlocal completed_this_run, failed_this_run

        try:
            await process_one(paper, global_idx, sem, download_lock, last_download_time)
        except Exception as e:
            async with state_lock:
                failed_this_run += 1
                # key 必须是索引号（str），水位线按索引推进
                state["failed"][str(global_idx)] = {
                    "arxiv_id": paper["arxiv_id"],
                    "error": str(e)[:200],
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                # 清理半成品
                paper_dir = DATA_DIR / paper["arxiv_id"]
                output_dir = paper_dir / "processed"
                if output_dir.exists():
                    shutil.rmtree(output_dir, ignore_errors=True)
                paper_md = paper_dir / "paper.md"
                if paper_md.exists():
                    paper_md.unlink()
                # 记录失败后推进水位线（失败不阻塞）
                _advance_watermark()

            print(f"❌ [{global_idx+1}/{total}] {paper['arxiv_id']} 失败: {e!s:.150}")
            return

        async with state_lock:
            completed_this_run += 1
            state["completed"] = state["completed"] + 1
            ahead = set(state.get("ahead", []))
            ahead.add(global_idx)
            state["ahead"] = sorted(ahead)
            _advance_watermark()

        elapsed = time.time() - start_time
        rate = (completed_this_run + failed_this_run) / elapsed * 60 if elapsed > 0 else 0
        print(f"✅ [{global_idx+1}/{total}] {paper['arxiv_id']} "
              f"({completed_this_run} ok, {failed_this_run} fail, "
              f"{elapsed:.0f}s elapsed, {rate:.1f}/min)")

    # asyncio.create_task 并发执行，按完成顺序收拢
    tasks = [
        asyncio.create_task(process_one_with_state(paper, start_idx + i))
        for i, paper in enumerate(papers)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    # ── 收尾 ────────────────────────────────────────────
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🏁 本轮完成")
    print(f"   ✅ 成功: {completed_this_run}")
    print(f"   ❌ 失败: {failed_this_run}")
    print(f"   ⏱️  耗时: {elapsed:.0f}s ({elapsed/3600:.1f}h)")
    print(f"   📍 进度: {state['next_index']}/{total}")
    print(f"{'='*60}")

    if state["next_index"] >= total:
        print("🎉 全部论文处理完毕")
        state_path.unlink(missing_ok=True)
    else:
        print(f"💾 断点已保存 → 下次从第 {state['next_index']} 篇继续")


if __name__ == "__main__":
    asyncio.run(main())
