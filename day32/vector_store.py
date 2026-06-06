import psycopg2
import numpy as np
from embeddings import embed_text, embed_batch  # 复用day31的工具
import os
os.environ["PGCLIENTENCODING"] = "utf8"



# 数据库连接（改成你自己的配置）
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chat_db",
    "user": "chat_user",
    "password": "188160",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def init_table():
    """创建存储向量的表"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id        SERIAL PRIMARY KEY,
                    content   TEXT NOT NULL,
                    embedding vector(512)   -- bge-small 是512维
                );
            """)
            conn.commit()
    print("表创建成功")


def insert_documents(texts: list[str]):
    """批量写入文本 + 向量"""
    vectors = embed_batch(texts)
    with get_conn() as conn:
        with conn.cursor() as cur:
            for text, vec in zip(texts, vectors):
                cur.execute(
                    "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
                    (text, vec)
                )
        conn.commit()
    print(f"写入 {len(texts)} 条文档")


def search(query: str, top_k: int = 3):
    """语义搜索：找最相似的 top_k 条"""
    query_vec = embed_text(query)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT content,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM documents
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """, (query_vec, query_vec, top_k))
            return cur.fetchall()


if __name__ == "__main__":
    # 1. 初始化
    init_table()

    # 2. 写入一批知识
    docs = [
        "猫是一种常见的宠物，喜欢吃鱼和猫粮",
        "狗是人类最忠实的朋友，喜欢啃骨头",
        "Python是一种简洁易学的编程语言",
        "PostgreSQL是功能强大的开源关系型数据库",
        "向量数据库用于存储和检索高维向量",
        "深度学习是机器学习的一个子领域",
        "今天上海天气晴朗，气温25度",
        "RAG技术结合了检索和生成两种能力",
    ]
    insert_documents(docs)

    # 3. 语义搜索测试
    queries = ["我想养一只宠物", "数据库有哪些类型", "AI相关技术"]
    for q in queries:
        print(f"\n查询：「{q}」")
        results = search(q, top_k=2)
        for content, sim in results:
            print(f"  {sim:.4f}  {content}")