# ai.py
# ai.py

from openai import OpenAI
from config import settings

client = OpenAI(api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,)

def chat_with_ai(history: list[dict], model: str | None = None) -> dict:
    model = model or settings.DEFAULT_MODEL
    response = client.chat.completions.create(
        model=model,
        messages=history,
        max_tokens=1000,
    )
    return {
        "content":     response.choices[0].message.content,
        "token_count": response.usage.total_tokens,
    }