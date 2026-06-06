import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day31'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day32'))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from pypdf import PdfReader
import docx
from langchain_text_splitters import RecursiveCharacterTextSplitter
from embeddings import embed_batch


def get_conn():
    return psycopg2.connect(
        "postgresql://chat_user:188160@localhost:5432/chat_db"
    )


def init_table():
    """创建支持元数据的知识库表"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id         SERIAL PRIMARY KEY,
                    content    TEXT NOT NULL,
                    embedding  vector(512),
                    source     TEXT,        -- 来源文件名
                    chunk_index INT          -- 第几块
                );
            """)
            conn.commit()
    print("知识库表创建成功")


# ── 文档读取 ──────────────────────────────────────

def read_pdf(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_docx(path: str) -> str:
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_markdown(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_txt(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    readers = {
        ".pdf": read_pdf,
        ".docx": read_docx,
        ".md": read_markdown,
        ".txt": read_txt,
    }
    if ext not in readers:
        raise ValueError(f"不支持的文件类型: {ext}")
    return readers[ext](path)


# ── 分块 ──────────────────────────────────────────

def split_text(text: str, chunk_size=300, overlap=50) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""],
    )
    return splitter.split_text(text)


# ── 入库 ──────────────────────────────────────────

def ingest_file(path: str):
    """读取文件 → 分块 → 向量化 → 存库"""
    filename = os.path.basename(path)
    print(f"处理文件：{filename}")

    # 1. 读取
    text = read_file(path)
    print(f"  读取字符数：{len(text)}")

    # 2. 分块
    chunks = split_text(text)
    print(f"  分块数量：{len(chunks)}")

    # 3. 向量化
    vectors = embed_batch(chunks)

    # 4. 存库
    with get_conn() as conn:
        with conn.cursor() as cur:
            for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
                cur.execute("""
                    INSERT INTO knowledge_base
                        (content, embedding, source, chunk_index)
                    VALUES (%s, %s, %s, %s)
                """, (chunk, vec, filename, i))
        conn.commit()
    print(f"  成功写入 {len(chunks)} 块")


def search(query: str, top_k: int = 3) -> list[dict]:
    from embeddings import embed_text
    query_vec = embed_text(query)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT content, source, chunk_index,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM knowledge_base
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """, (query_vec, query_vec, top_k))
            rows = cur.fetchall()
    return [
        {"content": r[0], "source": r[1], "chunk": r[2], "score": r[3]}
        for r in rows
    ]


if __name__ == "__main__":
    init_table()

    # 创建测试文件
    test_file = "test_doc.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("""
人工智能简介

人工智能（AI）是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。
机器学习是AI的核心技术，通过数据训练模型来完成任务。
深度学习使用神经网络，在图像识别和自然语言处理方面取得了突破。

RAG技术

RAG（检索增强生成）是一种结合检索和生成的AI技术。
它首先从知识库中检索相关文档，然后将其注入到语言模型的提示中。
这种方法可以让AI回答基于特定知识库的问题，避免幻觉。

向量数据库

向量数据库专门用于存储和检索高维向量。
pgvector是PostgreSQL的向量扩展，支持余弦相似度和欧氏距离搜索。
常见的向量数据库还有Pinecone、Qdrant、Weaviate等。
        """)

    ingest_file(test_file)

    print("\n── 搜索测试 ──")
    queries = ["什么是机器学习", "RAG怎么工作的", "有哪些向量数据库"]
    for q in queries:
        print(f"\n查询：{q}")
        results = search(q, top_k=2)
        for r in results:
            print(f"  [{r['score']:.4f}] {r['source']} 块{r['chunk']}: {r['content'][:50]}...")