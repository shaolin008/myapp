import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day31'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day34'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day35'))

from dotenv import load_dotenv
load_dotenv()

import shutil
import psycopg2
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from document_loader import ingest_file, init_table
from hybrid_search import hybrid_search

app = FastAPI(title="知识库管理 API")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_conn():
    return psycopg2.connect(
        "postgresql://chat_user:188160@localhost:5432/chat_db"
    )


# ── 启动时初始化表 ────────────────────────────────

@app.on_event("startup")
async def startup():
    init_table()
    print("知识库已就绪")


# ── 上传文件入库 ──────────────────────────────────

@app.post("/kb/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并自动解析入库"""
    allowed = {".txt", ".pdf", ".docx", ".md"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    # 保存文件
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 入库
    try:
        ingest_file(save_path)
    except Exception as e:
        raise HTTPException(500, f"解析失败: {str(e)}")

    return {"message": f"{file.filename} 上传并入库成功"}


# ── 查询接口 ──────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    top_k: int = 3
    use_hybrid: bool = True


@app.post("/kb/search")
async def search(req: QueryRequest):
    """语义搜索知识库"""
    if not req.query.strip():
        raise HTTPException(400, "查询内容不能为空")

    results = hybrid_search(req.query, top_k=req.top_k)
    return {
        "query": req.query,
        "results": [
            {
                "content": r["content"],
                "source": r["source"],
                "score": round(r["fused_score"], 4),
            }
            for r in results
        ],
    }


# ── 列出所有文档 ──────────────────────────────────

@app.get("/kb/documents")
async def list_documents():
    """列出知识库中所有文件及块数"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, COUNT(*) as chunks
                FROM knowledge_base
                GROUP BY source
                ORDER BY source;
            """)
            rows = cur.fetchall()
    return {
        "total_sources": len(rows),
        "documents": [{"source": r[0], "chunks": r[1]} for r in rows]
    }


# ── 删除文档 ──────────────────────────────────────

@app.delete("/kb/documents/{filename}")
async def delete_document(filename: str):
    """按文件名删除知识库中的文档"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM knowledge_base WHERE source = %s;",
                (filename,)
            )
            deleted = cur.rowcount
        conn.commit()

    if deleted == 0:
        raise HTTPException(404, f"未找到文档: {filename}")

    return {"message": f"已删除 {filename}，共 {deleted} 块"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)