from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import asynccontextmanager
from .database import init_db
from .auth import router as auth_router
from .ai_qa import router as ai_qa_router
from .benchmark import router as benchmark_router

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="QA", lifespan=lifespan)
app.add_middleware(NoCacheMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

app.include_router(auth_router)
app.include_router(ai_qa_router)
app.include_router(benchmark_router)

# ── SPA 静态文件 + fallback ────────────────────────────────
DIST = Path(__file__).resolve().parent.parent / "frontend-web" / "dist"
if DIST.is_dir():
    # 先挂载 assets 子目录（Vite 打包产物），让 /assets/xxx 能直接命中文件
    assets = DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    # 对所有非 /api 的 GET 请求：有对应静态文件就返回文件，否则返回 index.html（SPA fallback）
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        file = DIST / full_path
        if full_path and file.is_file():
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
