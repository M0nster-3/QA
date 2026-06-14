"""
arxiv 元数据快照 · batch_index.py

按周切窗查询 arxiv 搜索 API，生成固定顺序的论文元数据索引。
独立一次性脚本，不嵌入主管道。
可调时间范围、可断点续传。

用法:
  python tools/batch_index.py                                    # 默认 2025-01-01 → 2026-06-01
  python tools/batch_index.py --start 2025-03-01 --end 2025-06-30
  python tools/batch_index.py --output /path/to/index.json
"""

import os, sys, json, time, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ── 默认配置 ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "server" / "data" / "papers" / "_batch_index.json"
DEFAULT_STATE  = PROJECT_ROOT / "server" / "data" / "papers" / "_batch_index_state.json"

ARXIV_API = "http://export.arxiv.org/api/query"
REQUEST_DELAY = 3.0
MAX_RESULTS_PER_PAGE = 500


# ═══════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════

def weeks_between(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """生成 [start, end] 之间的周窗口列表（从 start 起每 7 天一个窗口）。"""
    weeks = []
    cursor = start
    while cursor <= end:
        week_end = cursor + timedelta(days=6, hours=23, minutes=59, seconds=59)
        if week_end > end:
            week_end = end.replace(hour=23, minute=59, second=59)
        weeks.append((cursor, week_end))
        cursor = cursor + timedelta(days=7)
    return weeks


def fmt_date(d: datetime) -> str:
    """YYYYMMDDhhmmss 格式。"""
    return d.strftime("%Y%m%d%H%M%S")


def query_arxiv_window(from_date: datetime, to_date: datetime, start: int = 0) -> dict:
    """
    查询 arxiv API：指定时间窗口内 math 论文。
    返回 {"papers": [...], "total_hits": int}。
    """
    query = (
        f"cat:math.*"
        f" AND submittedDate:[{fmt_date(from_date)} TO {fmt_date(to_date)}]"
    )
    params = {
        "search_query": query,
        "start": start,
        "max_results": MAX_RESULTS_PER_PAGE,
        "sortBy": "submittedDate",
        "sortOrder": "ascending",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"

    # 重试 3 次（网络超时/503）
    xml_data = None
    last_error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ArxivWeb/1.0 (mailto:research@example.com)"},
            )
            resp = urllib.request.urlopen(req, timeout=120)
            xml_data = resp.read().decode("utf-8")
            break
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))  # 5s, 10s 退避
    if xml_data is None:
        raise RuntimeError(f"请求失败 (重试3次): {last_error}") from last_error

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    }
    root = ET.fromstring(xml_data)

    total_hits = 0
    total_el = root.find("opensearch:totalResults", ns)
    if total_el is not None:
        total_hits = int(total_el.text)

    papers = []
    for entry in root.findall("atom:entry", ns):
        arxiv_id_full = entry.find("atom:id", ns).text.strip()
        arxiv_id = arxiv_id_full.split("/")[-1]
        arxiv_id_clean = arxiv_id.split("v")[0]  # 去版本号

        title = " ".join(entry.find("atom:title", ns).text.strip().split())
        abstract = " ".join(entry.find("atom:summary", ns).text.strip().split())

        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.find("atom:name", ns)
            if name is not None:
                authors.append(name.text.strip())

        primary_cat = entry.find("arxiv:primary_category", ns)
        primary_category = primary_cat.get("term") if primary_cat is not None else ""

        categories = [cat.get("term") for cat in entry.findall("atom:category", ns)]

        published = entry.find("atom:published", ns)
        submitted_date = published.text.strip()[:10] if published is not None else ""

        papers.append({
            "arxiv_id": arxiv_id_clean,
            "title": title,
            "authors": ", ".join(authors),
            "abstract": abstract,
            "primary_category": primary_category,
            "categories": categories,
            "submitted_date": submitted_date,
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id_clean}",
        })

    return {"papers": papers, "total_hits": total_hits}


# ═══════════════════════════════════════════════════════════════
# 主逻辑
# ═══════════════════════════════════════════════════════════════

def load_state(state_path: Path) -> dict:
    """加载断点状态。只记录 last_week_to，去重 ID 从输出文件重建。"""
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {"last_week_to": None}


def save_state(state_path: Path, state: dict):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def query_arxiv_window_all(from_date: datetime, to_date: datetime) -> dict:
    """
    查询 arxiv API：指定时间窗口内全部 math 论文（自动翻页，直到拿完或到上限）。
    返回 {"papers": [...], "total_hits": int}。
    """
    all_papers = []
    start = 0
    total_hits = 0

    while True:
        result = query_arxiv_window(from_date, to_date, start)
        total_hits = result["total_hits"]
        all_papers.extend(result["papers"])

        if len(result["papers"]) == 0 or len(result["papers"]) < MAX_RESULTS_PER_PAGE:
            break
        start += MAX_RESULTS_PER_PAGE
        time.sleep(REQUEST_DELAY)

    return {"papers": all_papers, "total_hits": total_hits}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="arxiv 元数据快照 · 按周切窗")
    parser.add_argument("--start", default="2025-01-01", help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-06-01", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出 JSON 路径")
    parser.add_argument("--state", default=str(DEFAULT_STATE), help="断点状态文件路径")
    parser.add_argument("--resume", action="store_true", help="从上次中断处继续")
    parser.add_argument("--dry-run", action="store_true", help="只打印窗口信息，不发请求")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")

    # 生成周窗口
    all_weeks = weeks_between(start_date, end_date)
    print(f"📅 时间范围: {args.start} → {args.end}")
    print(f"📐 周窗口数: {len(all_weeks)}")
    print(f"⏱️  预计耗时: {len(all_weeks) * REQUEST_DELAY:.0f} 秒")

    if args.dry_run:
        for ws, we in all_weeks[:5]:
            print(f"  {ws.strftime('%Y-%m-%d')} → {we.strftime('%Y-%m-%d')}")
        print(f"  ... 共 {len(all_weeks)} 周")
        return

    # 断点续传
    state_path = Path(args.state)
    state = load_state(state_path) if args.resume else {"last_week_to": None}

    # 加载已有结果（去重 ID 从输出文件重建，不存 state）
    output_path = Path(args.output)
    all_papers: list[dict] = []
    ids_seen: set = set()
    if args.resume and output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        all_papers = existing
        ids_seen = {p["arxiv_id"] for p in existing}
        print(f"📂 续传模式: 已有 {len(all_papers)} 篇, {len(ids_seen)} 个去重 ID")

    # 跳过已完成的周
    last_done = state.get("last_week_to")
    weeks_to_process = all_weeks
    if last_done:
        weeks_to_process = [
            (ws, we) for ws, we in all_weeks
            if we > datetime.fromisoformat(last_done)
        ]
        print(f"⏭️  跳过 {len(all_weeks) - len(weeks_to_process)} 个已完成窗口")

    print(f"\n{'='*60}")
    print(f"🔍 开始查询 {len(weeks_to_process)} 个周窗口")
    print(f"{'='*60}\n")

    for wi, (ws, we) in enumerate(weeks_to_process):
        window_label = f"{ws.strftime('%Y-%m-%d')} → {we.strftime('%Y-%m-%d')}"
        print(f"[{wi+1}/{len(weeks_to_process)}] {window_label}", end=" ", flush=True)

        try:
            result = query_arxiv_window_all(ws, we)
            new_papers = [p for p in result["papers"] if p["arxiv_id"] not in ids_seen]
            all_papers.extend(new_papers)
            ids_seen.update(p["arxiv_id"] for p in new_papers)
            print(f"→ {result['total_hits']} hits, {len(new_papers)} 新入库 (总计 {len(all_papers)})")

        except Exception as e:
            print(f"→ ❌ 失败: {e}")
            # 保存当前进度后退出
            state["last_week_to"] = ws.strftime("%Y-%m-%d") if wi > 0 else None
            save_state(state_path, state)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(all_papers, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"\n💾 断点已保存 (last_week_to={state['last_week_to']}, 总计{len(all_papers)}篇)")
            print(f"   下次运行: python tools/batch_index.py --resume")
            sys.exit(1)

        # 更新断点
        state["last_week_to"] = we.strftime("%Y-%m-%d")
        save_state(state_path, state)

        # 请求间隔
        if wi < len(weeks_to_process) - 1:
            time.sleep(REQUEST_DELAY)

    # 按提交日期排序（保证固定顺序）
    all_papers.sort(key=lambda p: (p.get("submitted_date", ""), p["arxiv_id"]))

    # 写入最终产物
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(all_papers, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\n{'='*60}")
    print(f"✅ 元数据快照完成")
    print(f"📄 总计: {len(all_papers)} 篇论文")
    print(f"📂 输出: {output_path}")
    print(f"{'='*60}")
    # 清理状态文件
    state_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
