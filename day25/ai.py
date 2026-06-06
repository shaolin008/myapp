# ai.py
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

def chat_with_ai(history: list[dict], model: str = "deepseek-v4-pro[1m]") -> dict:
    """
    传入完整对话历史，返回 AI 回复和 token 用量
    history 格式：[{"role": "user", "content": "..."}, ...]
    """
    response = client.chat.completions.create(
        model=model,
        messages=history,
        max_tokens=1000,
    )
    return {
        "content":     response.choices[0].message.content,
        "token_count": response.usage.total_tokens,
    }