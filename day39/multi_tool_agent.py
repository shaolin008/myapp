import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day31'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day35'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day37'))

from dotenv import load_dotenv
load_dotenv()

import json
from datetime import datetime
from openai import OpenAI
from function_calling import call_tool, TOOLS as BASE_TOOLS
from hybrid_search import hybrid_search

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# ── 新增工具定义 ──────────────────────────────────

NEW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "把内容写入文件保存到本地，当用户需要保存报告、笔记、总结时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "文件名，如 report.txt"},
                    "content": {"type": "string", "description": "要写入的内容"},
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "文件名"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出当前目录下的所有文件",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_knowledge",
            "description": "搜索知识库并生成结构化摘要，适合需要整理知识点时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "要整理的主题"},
                    "top_k": {"type": "integer", "default": 5}
                },
                "required": ["topic"]
            }
        }
    },
]

ALL_TOOLS = BASE_TOOLS + NEW_TOOLS

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── 新增工具实现 ──────────────────────────────────

def write_file(filename: str, content: str) -> str:
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入文件：{path}（{len(content)} 字符）"


def read_file(filename: str) -> str:
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return f"文件不存在：{path}"
    with open(path, encoding="utf-8") as f:
        return f.read()


def list_files() -> str:
    files = os.listdir(OUTPUT_DIR)
    if not files:
        return "outputs 目录为空"
    return "\n".join(files)


def summarize_knowledge(topic: str, top_k: int = 5) -> str:
    results = hybrid_search(topic, top_k=top_k)
    if not results:
        return f"知识库中没有关于「{topic}」的内容"
    lines = [f"关于「{topic}」的知识库内容：\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r['fused_score']:.2f}] {r['content']}")
    return "\n".join(lines)


def call_all_tools(name: str, args: dict) -> str:
    """扩展后的工具分发"""
    dispatch = {
        "write_file": write_file,
        "read_file": read_file,
        "list_files": list_files,
        "summarize_knowledge": summarize_knowledge,
    }
    if name in dispatch:
        return dispatch[name](**args)
    return call_tool(name, args)  # 回退到 day37 的工具


# ── Agent 主循环 ──────────────────────────────────

def agent(user_message: str, max_steps: int = 8) -> str:
    print(f"\n{'='*55}")
    print(f"用户：{user_message}")
    print('='*55)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个能干的工作助手，可以搜索知识库、"
                "做计算、读写文件。遇到复杂任务拆分步骤完成，"
                "完成后给用户清晰的总结。"
            )
        },
        {"role": "user", "content": user_message},
    ]

    step = 0
    while step < max_steps:
        step += 1
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if msg.content:
            print(f"\n💭 {msg.content[:120]}")

        if not msg.tool_calls:
            print(f"\n✅ 完成（共 {step} 步）")
            return msg.content

        messages.append(msg)
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"🔧 {name}({args})")
            result = call_all_tools(name, args)
            print(f"👁  {result[:100]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "已达到最大步骤数"


if __name__ == "__main__":
    # 任务一：整理知识库内容并保存成文件
    agent(
        "帮我把知识库里关于Python和FastAPI的内容整理成一份学习笔记，"
        "保存到 python_notes.txt"
    )

    # 任务二：计算 + 写报告
    agent(
        "我每天学习3小时，已经学了39天，"
        "计算一下总学习时长，然后生成一份学习报告保存到 study_report.txt"
    )

    # 任务三：读取刚才保存的文件
    agent("读取 study_report.txt 的内容，给我一个简短总结")