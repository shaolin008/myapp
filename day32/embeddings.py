import numpy as np
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
load_dotenv()

model = SentenceTransformer("BAAI/bge-small-zh-v1.5")

def embed_text(text: str) -> list[float]:
    return model.encode(text, normalize_embeddings=True).tolist()

def embed_batch(texts: list[str]) -> list[list[float]]:
    return model.encode(texts, normalize_embeddings=True).tolist()

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
if __name__ == "__main__":
    sentences = [
        "猫喜欢吃鱼",
        "猫爱吃鱼",
        "狗喜欢啃骨头",
        "今天股票大涨",
        "量子力学的基本原理",
    ]

    vectors = embed_batch(sentences)
    base = vectors[0]

    print("以「猫喜欢吃鱼」为基准：\n")
    for sentence, vec in zip(sentences, vectors):
        sim = cosine_similarity(base, vec)
        bar = "█" * int(sim * 20)
        print(f"{sim:.4f}  {bar:20s}  {sentence}")