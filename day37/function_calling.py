import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day31'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day35'))

from dotenv import load_dotenv
load_dotenv()

import json
from openai import OpenAI
from hybrid_search import hybrid_search

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# ── 定义工具 ──────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "从知识库中搜索相关信息，当用户问题需要查阅资料时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认3",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "执行数学计算，当用户需要计算数字时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，例如：2 + 3 * 4"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前时间",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# ── 工具实现 ──────────────────────────────────────

def search_knowledge_base(query: str, top_k: int = 3) -> str:
    results = hybrid_search(query, top_k=top_k)
    if not results:
        return "知识库中没有找到相关信息"
    return "\n".join(
        f"[{r['fused_score']:.2f}] {r['content']}" for r in results
    )


def calculate(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {e}"


def get_current_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def call_tool(name: str, args: dict) -> str:
    """根据工具名称分发调用"""
    if name == "search_knowledge_base":
        return search_knowledge_base(**args)
    elif name == "calculate":
        return calculate(**args)
    elif name == "get_current_time":
        return get_current_time()
    return f"未知工具: {name}"


# ── Agent 主循环 ──────────────────────────────────

def agent(user_message: str) -> str:
    print(f"\n用户：{user_message}")
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message

        # AI 直接回答，不需要调用工具
        if not msg.tool_calls:
            print(f"AI：{msg.content}")
            return msg.content

        # AI 要调用工具
        messages.append(msg)

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"  → 调用工具：{name}({args})")

            result = call_tool(name, args)
            print(f"  ← 工具返回：{result[:80]}...")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })


if __name__ == "__main__":
    questions = [
        "现在几点了？",
        "1234 * 5678 等于多少？",
        "知识库里有关于Python的内容吗？",
        "今天几点了，另外帮我算一下 99 * 88",  # 同时调用两个工具
    ]

    for q in questions:
        agent(q)
        print("-" * 50)