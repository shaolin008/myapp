import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day31'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day35'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'day37'))

from dotenv import load_dotenv
load_dotenv()

import json
from openai import OpenAI
from function_calling import TOOLS, call_tool

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = """你是一个智能助手，使用 ReAct 模式解决问题。

遇到复杂问题时，你应该：
1. 先思考需要哪些信息
2. 调用合适的工具获取信息
3. 根据结果继续思考或给出最终答案

可用工具：
- search_knowledge_base：搜索知识库
- calculate：数学计算
- get_current_time：获取当前时间

请认真思考每一步，不要跳过推理过程。"""


def react_agent(user_message: str, max_steps: int = 5) -> str:
    print(f"\n{'='*55}")
    print(f"用户：{user_message}")
    print('='*55)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    step = 0
    while step < max_steps:
        step += 1
        print(f"\n[步骤 {step}]")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message

        # 有思考内容就打印
        if msg.content:
            print(f"💭 思考：{msg.content}")

        # 没有工具调用，直接输出最终答案
        if not msg.tool_calls:
            print(f"\n✅ 最终答案：{msg.content}")
            return msg.content

        # 执行工具调用
        messages.append(msg)
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"🔧 行动：{name}({args})")

            result = call_tool(name, args)
            print(f"👁  观察：{result[:100]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "已达到最大步骤数"


if __name__ == "__main__":
    # 简单问题：一步解决
    react_agent("现在几点？")

    # 中等问题：需要查询再回答
    react_agent("知识库里有FastAPI的内容吗？它有什么特点？")

    # 复杂问题：多步推理
    react_agent(
        "我有100元，FastAPI相关的书定价是原价的8折，"
        "原价88元，我买完还剩多少钱？"
        "另外告诉我知识库里关于FastAPI的描述。"
    )