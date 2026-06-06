from fastapi import FastAPI
import json
import time
from pydantic import BaseModel, Field
from typing import Optional

from langchain_core.tools import StructuredTool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ========== 1. 全局数据 ==========

persons = {}
next_id = 1
pending_reviews = []
process_instances = {}

# 任务清单
ONBOARDING_TASKS = [
    {"name": "添加人员档案", "need_review": False},
    {"name": "分配工号", "need_review": False},
    {"name": "创建系统账号", "need_review": True},
    {"name": "分配部门权限", "need_review": True},
    {"name": "发送欢迎邮件", "need_review": False}
]

# 流程模板库
PROCESS_TEMPLATES = {
    "employee_onboarding": {
        "name": "employee_onboarding",
        "display_name": "员工入职流程",
        "triggers": ["入职", "新员工", "办理入职"],
        "required_params": ["name", "age", "department"],
        "steps": ONBOARDING_TASKS
    }
}

RETRY_CONFIG = {"max_retries": 3, "retry_delay": 1}


# ========== 2. 数据持久化 ==========

def save_data():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({
            "next_id": next_id,
            "persons": persons,
            "pending_reviews": pending_reviews,
            "process_instances": process_instances
        }, f, ensure_ascii=False, indent=2)


def load_data():
    global next_id, persons, pending_reviews, process_instances
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            next_id = data.get("next_id", 1)
            persons = {int(k): v for k, v in data.get("persons", {}).items()}
            pending_reviews = data.get("pending_reviews", [])
            process_instances = data.get("process_instances", {})
    except FileNotFoundError:
        pass


load_data()


# ========== 3. 审核系统 ==========

def create_review_task(operation: str, params: dict, ai_analysis: str):
    task = {
        "id": f"review_{len(pending_reviews) + 1}",
        "operation": operation,
        "params": params,
        "ai_analysis": ai_analysis,
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
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


# ========== 4. 流程管理 ==========

def create_process(name: str, age: int, department: str):
    process_id = f"proc_{len(process_instances) + 1}_{int(time.time())}"
    process = {
        "id": process_id,
        "person_data": {"name": name, "age": age, "department": department},
        "tasks": [t.copy() for t in ONBOARDING_TASKS],
        "current_step": 0,
        "status": "running",
        "results": [],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "error": None
    }
    process_instances[process_id] = process
    save_data()
    return process


def get_process(process_id: str):
    return process_instances.get(process_id)


def update_process(process_id: str, updates: dict = None):
    if process_id in process_instances:
        if updates:
            process_instances[process_id].update(updates)
        process_instances[process_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_data()
        return process_instances[process_id]
    return None


def visualize_process(process):
    steps = process["tasks"]
    current = process["current_step"]
    progress_bar = ""
    step_details = []

    for i, task in enumerate(steps):
        if i < current:
            icon = "✅"
            status = "completed"
        elif i == current:
            if process["status"] == "paused":
                icon = "⏸️"
                status = "waiting_review"
            elif process["status"] == "failed":
                icon = "❌"
                status = "failed"
            else:
                icon = "▶️"
                status = "running"
        else:
            icon = "⏳"
            status = "pending"

        progress_bar += f"{icon} "
        step_details.append({
            "step": i + 1,
            "name": task["name"],
            "status": status,
            "icon": icon
        })

    progress_percent = int((current / len(steps)) * 100) if steps else 0

    return {
        "process_id": process["id"],
        "person_name": process["person_data"]["name"],
        "progress_bar": progress_bar.strip(),
        "progress_percent": progress_percent,
        "current_step": current + 1,
        "total_steps": len(steps),
        "status": process["status"],
        "step_details": step_details,
        "timeline": {
            "created_at": process["created_at"],
            "updated_at": process["updated_at"]
        },
        "error": process.get("error")
    }


# ========== 5. 任务执行 ==========

def execute_task_directly(task_name: str, person_data: dict):
    global next_id

    if task_name == "添加人员档案":
        person_id = next_id
        persons[person_id] = {
            "id": person_id,
            "name": person_data["name"],
            "age": person_data["age"],
            "dep": person_data["department"]
        }
        next_id += 1
        save_data()
        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"person_id": person_id},
            "message": f"✅ 已创建人员档案"
        }

    elif task_name == "分配工号":
        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"employee_number": f"EMP{next_id:04d}"},
            "message": "✅ 已分配工号"
        }

    elif task_name == "发送欢迎邮件":
        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"email_sent": True},
            "message": "✅ 已发送欢迎邮件"
        }

    return {
        "task_name": task_name,
        "status": "completed",
        "data": {},
        "message": f"✅ 已完成：{task_name}"
    }


def execute_current_task(process):
    step_index = process["current_step"]
    task = process["tasks"][step_index]
    task_name = task["name"]

    if task["need_review"]:
        ai_analysis = f"流程审核：{task_name}\n人员：{process['person_data']['name']}"
        task_id = create_review_task(
            operation=task_name,
            params=process["person_data"],
            ai_analysis=ai_analysis
        )

        result = {
            "task_name": task_name,
            "status": "pending_review",
            "task_id": task_id,
            "message": "⏸️ 需要审核"
        }
        process["results"].append(result)
        process["status"] = "paused"
        update_process(process["id"])

        return {
            "action": "pause",
            "message": f"任务'{task_name}'需要审核",
            "review_task_id": task_id
        }

    result = execute_task_directly(task_name, process["person_data"])
    process["results"].append(result)
    process["current_step"] += 1
    update_process(process["id"])

    return {
        "action": "continue",
        "result": result
    }


# ========== 6. AI Tools ==========

def start_process_tool(
        process_type: str,
        name: str,
        age: Optional[int] = None,
        department: Optional[str] = None,
        employee_id: Optional[int] = None
) -> str:
    """启动业务流程"""
    if process_type not in PROCESS_TEMPLATES:
        return f"❌ 未知流程类型：{process_type}"

    if process_type == "employee_onboarding":
        if not age or not department:
            return "❌ 入职流程需要：姓名、年龄、部门"

        process = create_process(name, age, department)
        execution_log = []

        while process["current_step"] < len(process["tasks"]):
            result = execute_current_task(process)
            execution_log.append(result)

            if result["action"] == "pause":
                viz = visualize_process(process)
                return f"""✅ 已为 {name} 启动入职流程
流程ID: {process['id']}
进度: {viz['progress_bar']}
完成度: {viz['progress_percent']}%
当前状态: 等待审核 - {result['review_task_id']}
下一步: 需要管理员审批'{process['tasks'][process['current_step']]['name']}'"""

            if result["action"] == "fail":
                return f"❌ 流程失败：{result['error']}"

        process["status"] = "completed"
        update_process(process["id"])
        return f"✅ {name} 的入职流程已全部完成！"

    return "❌ 未实现的流程"


def query_process_tool(process_id: Optional[str] = None) -> str:
    """查询流程状态"""
    if process_id:
        process = get_process(process_id)
        if not process:
            return f"❌ 流程不存在：{process_id}"

        viz = visualize_process(process)
        return f"""📊 流程详情
流程ID: {viz['process_id']}
员工: {viz['person_name']}
进度: {viz['progress_bar']}
完成度: {viz['progress_percent']}%
状态: {viz['status']}"""
    else:
        active = [p for p in process_instances.values()
                  if p["status"] in ["running", "paused"]]

        if not active:
            return "当前没有正在执行的流程"

        result = f"📋 当前有 {len(active)} 个活跃流程：\n\n"
        for proc in active:
            viz = visualize_process(proc)
            result += f"{viz['process_id']} - {viz['person_name']}: {viz['progress_percent']}% {viz['status']}\n"

        return result


def approve_review_tool(review_task_id: str) -> str:
    """批准审核任务"""
    task = approve_review(review_task_id)
    if not task:
        return f"❌ 审核任务不存在：{review_task_id}"

    for proc in process_instances.values():
        if proc["status"] == "paused":
            proc["current_step"] += 1
            proc["status"] = "running"
            update_process(proc["id"])

            while proc["current_step"] < len(proc["tasks"]):
                result = execute_current_task(proc)

                if result["action"] == "pause":
                    viz = visualize_process(proc)
                    return f"""✅ 审核已批准，流程继续执行
进度: {viz['progress_bar']}
完成度: {viz['progress_percent']}%
再次暂停: 等待审核 - {result['review_task_id']}"""

                if result["action"] == "fail":
                    return f"❌ 流程失败：{result['error']}"

            proc["status"] = "completed"
            update_process(proc["id"])
            return "✅ 审核已批准，流程已全部完成！"

    return "✅ 审核已批准"


tools = [
    StructuredTool.from_function(
        func=start_process_tool,
        name="start_process",
        description="启动业务流程。employee_onboarding需要name,age,department"
    ),
    StructuredTool.from_function(
        func=query_process_tool,
        name="query_process",
        description="查询流程状态"
    ),
    StructuredTool.from_function(
        func=approve_review_tool,
        name="approve_review",
        description="批准审核任务"
    )
]

# ========== 7. Agent 配置 ==========

llm = ChatOpenAI(
    api_key="sk-eyy7q4sejyOBK9FgbxjfHVmcPiw3ttLXR05FTMMilK9gFGFB",
    base_url="https://api.moonshot.cn/v1",
    model="moonshot-v1-8k",
    temperature=0
)

AGENT_SYSTEM_PROMPT = """你是企业业务流程助理。

能力：
1. 启动入职流程（需要：姓名、年龄、部门）
2. 查询流程状态
3. 批准审核

规则：
- 用户提到"入职"时，用 start_process，process_type="employee_onboarding"
- 缺少参数时主动询问
- 用户说"查看"、"状态"时，用 query_process
- 用户说"批准"时，用 approve_review
- 回复要简洁清晰"""

prompt = ChatPromptTemplate.from_messages([
    ("system", AGENT_SYSTEM_PROMPT),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
)

# ========== 8. FastAPI ==========

app = FastAPI()


def success(data=None, msg="ok"):
    return {"code": 0, "msg": msg, "data": data}


def error(msg="error", code=1):
    return {"code": code, "msg": msg, "data": None}


@app.get("/")
def root():
    return {"message": "DAY 16 AI 驱动的流程管理系统"}


@app.get("/api/chat/simple")
def simple_chat(message: str):
    """对话接口"""
    try:
        result = agent_executor.invoke({"input": message})
        return success({
            "message": message,
            "response": result["output"]
        })
    except Exception as e:
        return error(str(e))


@app.get("/persons")
def list_persons():
    return success(persons)


@app.get("/api/processes")
def list_processes():
    processes = []
    for proc_id, proc in process_instances.items():
        viz = visualize_process(proc)
        processes.append(viz)
    return success(processes)


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("🚀 DAY 16 AI 驱动的流程管理系统")
    print("=" * 60)
    print("✨ 新功能：对话式流程操作")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)