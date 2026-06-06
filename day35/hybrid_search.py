import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day31'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day34'))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
import jieba
from rank_bm25 import BM25Okapi
from embeddings import embed_text

def get_conn():
    return psycopg2.connect(
        "postgresql://chat_user:188160@localhost:5432/chat_db"
    )


def get_all_docs() -> list[dict]:
    """从数据库取出所有文档"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content, source FROM knowledge_base;")
            rows = cur.fetchall()
    return [{"id": r[0], "content": r[1], "source": r[2]} for r in rows]


def vector_search(query: str, top_k: int = 5) -> list[dict]:
    """向量搜索"""
    query_vec = embed_text(query)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, content, source,
                       1 - (embedding <=> %s::vector) AS score
                FROM knowledge_base
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """, (query_vec, query_vec, top_k))
            rows = cur.fetchall()
    return [{"id": r[0], "content": r[1], "source": r[2], "score": r[3]} for r in rows]


def bm25_search(query: str, docs: list[dict], top_k: int = 5) -> list[dict]:
    """BM25 关键词搜索（中文分词）"""
    tokenized_docs = [list(jieba.cut(d["content"])) for d in docs]
    tokenized_query = list(jieba.cut(query))

    bm25 = BM25Okapi(tokenized_docs)
    scores = bm25.get_scores(tokenized_query)

    ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    return [{"id": d["id"], "content": d["content"],
             "source": d["source"], "score": float(s)}
            for s, d in ranked[:top_k]]


def hybrid_search(query: str, top_k: int = 3,
                  vector_weight: float = 0.6,
                  bm25_weight: float = 0.4) -> list[dict]:
    """融合向量搜索和BM25，RRF加权排序"""
    docs = get_all_docs()

    v_results = vector_search(query, top_k=len(docs))
    b_results = bm25_search(query, docs, top_k=len(docs))

    # 归一化分数到 0-1
    def normalize(results):
        scores = [r["score"] for r in results]
        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            return {r["id"]: 0.5 for r in results}
        return {r["id"]: (r["score"] - min_s) / (max_s - min_s)
                for r in results}

    v_norm = normalize(v_results)
    b_norm = normalize(b_results)

    # 融合
    all_ids = set(v_norm) | set(b_norm)
    fused = {}
    for doc_id in all_ids:
        v_score = v_norm.get(doc_id, 0) * vector_weight
        b_score = b_norm.get(doc_id, 0) * bm25_weight
        fused[doc_id] = v_score + b_score

    # 按融合分数排序
    top_ids = sorted(fused, key=fused.get, reverse=True)[:top_k]
    id_to_doc = {d["id"]: d for d in docs}

    return [
        {**id_to_doc[i], "fused_score": fused[i]}
        for i in top_ids if i in id_to_doc
    ]


if __name__ == "__main__":
    # 对比测试：纯向量 vs 混合检索
    queries = [
        "pgvector怎么用",      # 精确词，BM25 应该更有优势
        "AI可以做什么",        # 语义查询，向量更有优势
        "检索增强生成",        # 两者都能找到
    ]

    for q in queries:
        print(f"\n{'='*50}")
        print(f"查询：{q}")

        print("\n[纯向量搜索]")
        for r in vector_search(q, top_k=2):
            print(f"  {r['score']:.4f}  {r['content'][:40]}...")

        print("\n[混合检索]")
        for r in hybrid_search(q, top_k=2):
            print(f"  {r['fused_score']:.4f}  {r['content'][:40]}...")