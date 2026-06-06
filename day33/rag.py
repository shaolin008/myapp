import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day31'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day32'))

from dotenv import load_dotenv

load_dotenv()

import psycopg2
from openai import OpenAI
from embeddings import embed_text

# DeepSeek 客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


def get_conn():
    return psycopg2.connect(
        "postgresql://chat_user:188160@localhost:5432/chat_db"
    )


def retrieve(query: str, top_k: int = 3) -> list[str]:
    """从数据库检索最相关的文档片段"""
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
            rows = cur.fetchall()
    return [row[0] for row in rows]


def generate(query: str, context_docs: list[str]) -> str:
    """把检索结果注入 prompt，让 DeepSeek 生成回答"""
    context = "\n".join(f"- {doc}" for doc in context_docs)
    prompt = f"""你是一个知识库助手，请根据以下参考资料回答用户问题。
如果参考资料中没有相关信息，请直接说不知道，不要编造。

参考资料：
{context}

用户问题：{query}

回答："""

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content


def rag(query: str) -> str:
    """完整 RAG 流程"""
    print(f"\n问题：{query}")

    # 1. 检索
    docs = retrieve(query, top_k=3)
    print(f"检索到 {len(docs)} 条相关文档：")
    for doc in docs:
        print(f"  · {doc}")

    # 2. 生成
    answer = generate(query, docs)
    print(f"\n回答：{answer}")
    return answer


if __name__ == "__main__":
    questions = [
        "我适合养什么宠物？",
        "RAG是什么技术？",
        "今天天气怎么样？",  # 知识库里有这条
        "火星上有生命吗？",  # 知识库里没有，测试拒答
    ]
    for q in questions:
        rag(q)
        print("-" * 50)