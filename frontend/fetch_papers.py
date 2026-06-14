"""
Step 1 · arxiv 数据获取脚本

从 arxiv API 拉取数学论文元数据，下载 PDF，生成 source.json 骨架。

用法:
  python fetch_papers.py                    # 拉取 100 篇并下载前 10 篇
  python fetch_papers.py --max 50           # 拉取 50 篇元数据
  python fetch_papers.py --download 5       # 下载 5 篇 PDF
  python fetch_papers.py --id 2501.12345    # 下载指定论文
"""

import os, sys, json, time, shutil, re, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "server" / "data" / "papers"

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_PDF = "https://arxiv.org/pdf"          # PDF 下载端点
REQUEST_DELAY = 3.0  # arxiv 官方要求的请求间隔


# ═══════════════════════════════════════════════════════════════
# arxiv API 查询
# ═══════════════════════════════════════════════════════════════

def search_arxiv(max_results: int = 100, start: int = 0) -> list[dict]:
    """搜索 arxiv math 分类 2025+ 论文，返回元数据列表。"""
    query = "cat:math.* AND submittedDate:[202501010000 TO 202612312359]"
    url = f"{ARXIV_API}?search_query={urllib.request.quote(query)}&start={start}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"

    print(f"🔍 查询 arxiv API (max_results={max_results}, start={start})...")
    print(f"   URL: {url[:120]}...")

    xml_data = None
    last_error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ArxivWeb/1.0 (mailto:research@example.com)"})
            resp = urllib.request.urlopen(req, timeout=120)
            xml_data = resp.read().decode("utf-8")
            break
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    if xml_data is None:
        raise RuntimeError(f"arxiv API 请求失败 (重试3次): {last_error}") from last_error

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(xml_data)

    papers = []
    for entry in root.findall("atom:entry", ns):
        arxiv_id_full = entry.find("atom:id", ns).text.strip()
        arxiv_id = arxiv_id_full.split("/")[-1]
        arxiv_id_clean = re.sub(r"v\d+$", "", arxiv_id)

        title = " ".join(entry.find("atom:title", ns).text.strip().split())
        abstract = " ".join(entry.find("atom:summary", ns).text.strip().split())

        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.find("atom:name", ns)
            if name is not None:
                authors.append(name.text.strip())

        primary_cat = entry.find("arxiv:primary_category", ns)
        primary_category = primary_cat.get("term") if primary_cat is not None else ""

        categories = []
        for cat in entry.findall("atom:category", ns):
            categories.append(cat.get("term"))

        papers.append({
            "arxiv_id": arxiv_id_clean,
            "title": title,
            "authors": ", ".join(authors),
            "abstract": abstract,
            "primary_category": primary_category,
            "categories": categories,
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id_clean}",
        })

    print(f"   ✅ 获取到 {len(papers)} 篇论文元数据")
    return papers


# ═══════════════════════════════════════════════════════════════
# 下载 PDF
# ═══════════════════════════════════════════════════════════════

def download_paper(arxiv_id: str) -> bool:
    """下载一篇论文的 PDF，保存到 papers/{arxiv_id}/paper.pdf。"""
    paper_dir = DATA_DIR / arxiv_id
    pdf_path = paper_dir / "paper.pdf"

    if pdf_path.exists():
        print(f"   ⏭️ {arxiv_id}: paper.pdf 已存在，跳过下载")
        return True

    paper_dir.mkdir(parents=True, exist_ok=True)

    url = f"{ARXIV_PDF}/{arxiv_id}"
    print(f"   📥 下载 {arxiv_id}...")

    try:
        pdf_content = None
        last_error = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ArxivWeb/1.0 (mailto:research@example.com)"})
                resp = urllib.request.urlopen(req, timeout=120)
                pdf_content = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
        if pdf_content is None:
            raise RuntimeError(f"下载失败 (重试3次): {last_error}") from last_error
        if "html" in content_type:
            print(f"   ⚠️ {arxiv_id}: 无 PDF（返回 HTML），跳过")
            shutil.rmtree(paper_dir, ignore_errors=True)
            return False

        with open(pdf_path, "wb") as f:
            f.write(pdf_content)

        print(f"   ✅ 已保存 paper.pdf ({len(pdf_content)} bytes)")
        return True

    except Exception as e:
        print(f"   ❌ {arxiv_id}: 下载失败 - {e}")
        shutil.rmtree(paper_dir, ignore_errors=True)
        return False


# ═══════════════════════════════════════════════════════════════
# PDF 分割（用于并发 RW Agent）
# ═══════════════════════════════════════════════════════════════

CHUNK_PAGES = 10       # 每块页数


def split_pdf(pdf_path: Path) -> list[Path]:
    """将 PDF 按 CHUNK_PAGES 页切分，无重叠。返回每个 chunk PDF 的路径列表。"""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    if total <= CHUNK_PAGES:
        return [pdf_path]  # 太短，不分割

    chunk_dir = pdf_path.parent / "chunks"
    chunk_dir.mkdir(exist_ok=True)

    chunks = []
    for start in range(0, total, CHUNK_PAGES):
        end = min(start + CHUNK_PAGES, total)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        chunk_path = chunk_dir / f"chunk_{start:04d}-{end:04d}.pdf"
        writer.write(str(chunk_path))
        chunks.append(chunk_path)
        print(f"   📄 chunk: pages {start+1}-{end} → {chunk_path.name}")
    return chunks


# ═══════════════════════════════════════════════════════════════
# 生成 source.json 骨架
# ═══════════════════════════════════════════════════════════════

def create_source_json(paper: dict):
    """为论文生成 source.json 骨架（ai_keywords 留空）。"""
    paper_dir = DATA_DIR / paper["arxiv_id"]
    source_path = paper_dir / "source.json"

    if source_path.exists():
        return

    paper_dir.mkdir(parents=True, exist_ok=True)

    skeleton = {
        "arxiv_id": paper["arxiv_id"],
        "title": paper["title"],
        "authors": paper["authors"],
        "abstract": paper["abstract"],
        "primary_category": paper["primary_category"],
        "categories": paper["categories"],
        "arxiv_url": paper["arxiv_url"],
        "ai_keywords": [],
    }

    source_path.write_text(
        json.dumps(skeleton, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="arxiv 论文数据获取")
    parser.add_argument("--max", type=int, default=100, help="拉取元数据数量")
    parser.add_argument("--download", type=int, default=10, help="下载论文数量（从前 N 篇中选）")
    parser.add_argument("--id", type=str, help="下载指定论文 ID")
    parser.add_argument("--metadata-only", action="store_true", help="只拉元数据，不下载")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.id:
        # 单篇模式
        print(f"🔍 查询 arxiv API (id={args.id})...")
        id_url = f"{ARXIV_API}?id_list={args.id}"
        req = urllib.request.Request(id_url, headers={"User-Agent": "ArxivWeb/1.0 (mailto:research@example.com)"})
        resp = urllib.request.urlopen(req)
        xml_data = resp.read().decode("utf-8")
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(xml_data)
        entry = root.find("atom:entry", ns)

        skeleton = {
            "arxiv_id": args.id,
            "title": "",
            "authors": "",
            "abstract": "",
            "primary_category": "",
            "categories": [],
            "arxiv_url": f"https://arxiv.org/abs/{args.id}",
            "ai_keywords": [],
        }
        if entry is not None:
            skeleton["title"] = " ".join(entry.find("atom:title", ns).text.strip().split())
            skeleton["abstract"] = " ".join(entry.find("atom:summary", ns).text.strip().split())
            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None:
                    authors.append(name.text.strip())
            skeleton["authors"] = ", ".join(authors)
            primary_cat = entry.find("arxiv:primary_category", ns)
            if primary_cat is not None:
                skeleton["primary_category"] = primary_cat.get("term", "")
            skeleton["categories"] = [cat.get("term") for cat in entry.findall("atom:category", ns)]
            print(f"   ✅ 标题: {skeleton['title'][:80]}...")
        else:
            print(f"   ⚠️ 未查到元数据，使用空骨架")
        create_source_json(skeleton)
        success = download_paper(args.id)
        if success:
            print(f"✅ {args.id} 下载完成")
        else:
            print(f"❌ {args.id} 下载失败")
        return

    # 批量模式
    print(f"\n{'='*60}")
    print(f"📡 Step 1: 获取 arxiv 论文数据")
    print(f"{'='*60}\n")

    papers = search_arxiv(max_results=args.max)
    if not papers:
        print("❌ 未获取到论文")
        return

    index_path = DATA_DIR / "_papers_index.json"
    index_path.write_text(
        json.dumps(papers, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n📋 元数据已保存到 {index_path}")

    if args.metadata_only:
        print("✅ 仅元数据模式，不下载")
        return

    print(f"\n{'='*60}")
    print(f"📥 开始下载 PDF（最多 {args.download} 篇）")
    print(f"{'='*60}\n")

    downloaded = 0
    for i, paper in enumerate(papers):
        if downloaded >= args.download:
            break

        print(f"[{downloaded+1}/{args.download}] {paper['arxiv_id']}: {paper['title'][:80]}...")

        create_source_json(paper)
        success = download_paper(paper["arxiv_id"])
        if success:
            downloaded += 1

        if i < len(papers) - 1 and downloaded < args.download:
            time.sleep(REQUEST_DELAY)

    print(f"\n{'='*60}")
    print(f"✅ 下载完成: {downloaded} 篇论文")
    print(f"📂 数据目录: {DATA_DIR}")

    ready = [
        d.name for d in DATA_DIR.iterdir()
        if d.is_dir() and (d / "paper.pdf").exists() and (d / "source.json").exists()
    ]
    print(f"📋 可处理论文: {len(ready)} 篇")
    for r in ready:
        print(f"   • {r}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
