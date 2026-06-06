# main.py —— 运行这一个文件验证全部功能

from database import engine, Base
from models import Conversation, Message
from crud import save_conversation, get_history, list_conversations, update_title, delete_conversation

# 建表
Base.metadata.create_all(bind=engine)

print("=== 测试 1：保存一轮对话 ===")
conv_id = save_conversation(
    title="ORM 学习问答",
    model="gpt-4o",
    messages=[
        {"role": "user",      "content": "什么是 ORM？"},
        {"role": "assistant", "content": "ORM 是对象关系映射，用 Python 类操作数据库表。"},
        {"role": "user",      "content": "有什么优点？"},
        {"role": "assistant", "content": "代码更简洁，不用手写 SQL，还能防止注入攻击。"},
    ]
)
print(f"保存成功，id = {conv_id}")

print("\n=== 测试 2：查询历史 ===")
history = get_history(conv_id)
for msg in history:
    print(f"  [{msg['role']}] {msg['content']}")

print("\n=== 测试 3：更新标题 ===")
update_title(conv_id, "SQLAlchemy ORM 入门")
convs = list_conversations()
for c in convs:
    print(f"  #{c['id']} {c['title']} — {c['msg_count']} 条消息")

print("\n=== 测试 4：删除会话（级联删消息）===")
delete_conversation(conv_id)
print(f"删除后剩余会话数：{len(list_conversations())}")