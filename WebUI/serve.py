#!/usr/bin/env python3
"""
离线层 WebUI 启动器

用法:
    python serve.py              # 默认端口 8080
    python serve.py --port 9000  # 自定义端口

启动后在浏览器打开: http://localhost:8080/WebUI/
"""

import http.server
import json
import os
import sys
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORT = 8080


def generate_index() -> None:
    """扫描 server/data/papers/ 下已处理的论文，生成 _papers_ui.json。"""
    papers_dir = PROJECT_ROOT / "server" / "data" / "papers"
    index_path = papers_dir / "_papers_ui.json"

    if not papers_dir.exists():
        return

    docs = []
    for d in sorted(papers_dir.iterdir(), reverse=True):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        md_dir = d / "processed" / "md"
        source = d / "source.json"
        if not md_dir.exists():
            continue

        md_count = len(list(md_dir.glob("*.md")))

        # 读取 source.json 获取标题
        title = d.name
        keywords = []
        if source.exists():
            try:
                src = json.loads(source.read_text(encoding="utf-8"))
                title = src.get("title", d.name)
                keywords = src.get("ai_keywords", [])
            except Exception:
                pass

        docs.append({
            "arxiv_id": d.name,
            "title": title,
            "md_count": md_count,
            "keywords": keywords,
        })

    index_path.write_text(
        json.dumps(docs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  📋 发现 {len(docs)} 篇已处理论文 → server/data/papers/_papers_ui.json")


def main():
    global PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            PORT = int(sys.argv[idx + 1])

    os.chdir(PROJECT_ROOT)

    # 生成文档索引
    generate_index()

    handler = http.server.SimpleHTTPRequestHandler

    print(f"""
╔══════════════════════════════════════════════╗
║      离线层 · WebUI 启动器                   ║
╠══════════════════════════════════════════════╣
║  项目目录: {PROJECT_ROOT}
║  端口:     {PORT}
║  地址:     http://localhost:{PORT}/WebUI/
╚══════════════════════════════════════════════╝
""")

    url = f"http://localhost:{PORT}/WebUI/"
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print(f"  浏览器已打开: {url}")
    print(f"  按 Ctrl+C 停止服务器\n")

    with http.server.HTTPServer(("", PORT), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止")


if __name__ == "__main__":
    main()
