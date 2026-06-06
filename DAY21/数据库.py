import sqlite3
from datetime import datetime

DB_PATH = "chat_history.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # 让查询结果支持按列名访问
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL DEFAULT '新对话',
                model_name TEXT NOT NULL DEFAULT 'gpt-4o',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role            TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                content         TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                    ON DELETE CASCADE
            );
        """)

def save_conversation(title, model, messages: list[dict]) -> int:
    """一次性保存一轮完整对话，返回会话 id"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, model_name) VALUES (?, ?)",
            (title, model)
        )
        conv_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            [(conv_id, m["role"], m["content"]) for m in messages]
        )
    return conv_id

def get_history(conv_id: int) -> list[dict]:
    """查询某会话的所有消息，格式与 OpenAI API 兼容"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id",
            (conv_id,)
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]

def list_conversations():
    """列出所有会话及消息条数"""
    with get_conn() as conn:
        return conn.execute("""
            SELECT c.id, c.title, c.model_name,
                   COUNT(m.id) as msg_count, c.created_at
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id ORDER BY c.created_at DESC
        """).fetchall()

# ── 测试运行 ──────────────────────────────────
if __name__ == "__main__":
    init_db()

    conv_id = save_conversation(
        title="外键学习",
        model="gpt-4o",
        messages=[
            {"role": "user",      "content": "什么是外键？"},
            {"role": "assistant", "content": "外键是引用另一张表主键的字段，用来建立表间关联。"},
            {"role": "user",      "content": "ON DELETE CASCADE 是什么意思？"},
            {"role": "assistant", "content": "删除父行时自动删除所有关联的子行。"},
        ]
    )
    print(f"已保存会话 id={conv_id}")

    history = get_history(conv_id)
    for msg in history:
        print(f"  [{msg['role']}] {msg['content']}")

    print("\n所有会话：")
    for row in list_conversations():
        print(f"  #{row['id']} {row['title']} ({row['msg_count']} 条消息)")