from fastapi import FastAPI
import json
from pydantic import BaseModel
from langchain_core.tools import StructuredTool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate

# --- 1. 全局数据 ---
persons = {}
next_id = 1
pending_reviews = []  # 👈 新增


def save_data():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({
            "next_id": next_id,
            "persons": persons,
            "pending_reviews": pending_reviews  # 👈 新增
        }, f, ensure_ascii=False)


def load_data():
    global next_id, persons, pending_reviews
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            next_id = data.get("next_id", 1)
            persons = {int(k): v for k, v in data.get("persons", {}).items()}
            pending_reviews = data.get("pending_reviews", [])  # 👈 新增
    except FileNotFoundError:
        pass


load_data()


# --- 2. 审核系统函数 👈 新增 ---
def create_review_task(operation: str, params: dict, ai_analysis: str):
    task = {
        "id": f"review_{len(pending_reviews) + 1}",
        "operation": operation,
        "params": params,
        "ai_analysis": ai_analysis,
        "status": "pending",
        "created_at": "2025-02-09"
    }
    pending_reviews.append(task)
    save_data()
    return task["id"]


def get_pending_reviews():
    return [t for t in pending_reviews if t["status"] == "pending"]


def approve_review(task_id: str):
    for task in pending_reviews:
        if task["id"] == task_id:
            task["status"] = "approved"
            save_data()
            return task
    return None


# --- 3. LLM 和工具定义 ---
llm = ChatOpenAI(
    api_key="sk-eyy7q4sejyOBK9FgbxjfHVmcPiw3ttLXR05FTMMilK9gFGFB",
    base_url="https://api.moonshot.cn/v1",
    model="moonshot-v1-8k",
    temperature=0
)


def add_person_tool_func(name: str, age: int, department: str) -> str:
    global next_id
    person_id = next_id
    persons[person_id] = {
        "id": person_id,
        "name": name,
        "age": age,
        "dep": department
    }
    next_id += 1
    save_data()
    return f"成功添加人员：{name}"


def guarded_add_person(name: str, age: int, department: str) -> str:
    """👈 修改后的版本"""
    ai_analysis = f"""
AI 风险评估报告：
- 操作：添加人员
- 姓名：{name}
- 年龄：{age}
- 部门：{department}
- 风险等级：L2（高风险写操作）
- AI 建议：需检查是否重复添加
    """

    task_id = create_review_task(
        operation="add_person",
        params={"name": name, "age": age, "department": department},
        ai_analysis=ai_analysis
    )

    return f"✅ 添加请求已提交审核\n任务ID：{task_id}\n请管理员访问 GET /api/reviews 查看待审核任务"


add_person_tool = StructuredTool.from_function(
    func=guarded_add_person,
    name="add_person",
    description="添加人员（L2高风险操作，需人工审核）"
)

# --- 4. Agent 配置 ---
SAFETY_SYSTEM_PROMPT = """
你是企业内部 AI 助理，必须遵守以下规则：

1. 添加人员属于 L2 高风险写操作
2. 你只能生成审核任务，不能直接执行
3. 调用 add_person 工具会自动创建审核任务
4. 告知用户：任务已提交，需管理员审批
5. 不要尝试绕过审核机制
"""

tools = [add_person_tool]
base_prompt = hub.pull("hwchase17/openai-tools-agent")
prompt = ChatPromptTemplate.from_messages([
    ("system", SAFETY_SYSTEM_PROMPT),
    *base_prompt.messages
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# --- 5. FastAPI 应用 ---
app = FastAPI()


def add_person(name, age, dep):
    global next_id
    person_id = next_id
    next_id += 1
    persons[person_id] = {"id": person_id, "name": name, "age": age, "dep": dep}
    save_data()
    return person_id


def seek_person(person_id: int):
    return persons.get(person_id)


def success(data=None, msg="ok"):
    return {"code": 0, "msg": msg, "data": data}


def error(msg="error", code=1):
    return {"code": code, "msg": msg, "data": None}


class PersonCreate(BaseModel):
    name: str
    age: int
    dep: str


@app.post("/person")
def api_add_person(person: PersonCreate):
    pid = add_person(person.name, person.age, person.dep)
    return success({"id": pid})


@app.get("/person/{person_id}")
def api_get_person(person_id: int):
    person = seek_person(person_id)
    if not person:
        return error("not found")
    return success(person)


@app.get("/persons")
def api_list_persons():
    return success(persons)


# --- 6. 审核接口 👈 新增 ---
@app.get("/api/reviews")
def list_reviews():
    """查看所有待审核任务"""
    return success(get_pending_reviews())


@app.post("/api/reviews/{task_id}/approve")
def approve_task(task_id: str):
    """批准并执行任务"""
    task = approve_review(task_id)
    if not task:
        return error("任务不存在")

    if task["operation"] == "add_person":
        params = task["params"]
        pid = add_person(params["name"], params["age"], params["department"])
        return success({
            "message": "任务已批准并执行",
            "person_id": pid
        })

    return error("未知操作类型")


@app.post("/api/reviews/{task_id}/reject")
def reject_task(task_id: str, reason: str = "未提供原因"):
    """拒绝任务"""
    for task in pending_reviews:
        if task["id"] == task_id:
            task["status"] = "rejected"
            task["review_note"] = reason
            save_data()
            return success({"message": "任务已拒绝"})
    return error("任务不存在")


# --- 7. 启动 ---
if __name__ == "__main__":
    print(">>> Agent 已启动")
    while True:
        user_input = input("用户：")
        result = agent_executor.invoke({"input": user_input})
        print("AI：", result["output"])