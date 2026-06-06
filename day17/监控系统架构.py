from fastapi import FastAPI
import json
import time
from pydantic import BaseModel, Field
from typing import Optional

from langchain_core.tools import StructuredTool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ========== 1. 全局数据存储 ==========

persons = {}
next_id = 1
pending_reviews = []
process_instances = {}
reminders = []  # 👈 新增：提醒记录

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

# 👈 新增：监控配置
MONITOR_CONFIG = {
    "check_interval": 600,  # 检查间隔（秒）
    "review_timeout": 300,  # 审核超时阈值（秒），改为5分钟便于测试
    "process_timeout": 14400,  # 流程超时阈值（秒）
    "enable_auto_reminder": True
}

RETRY_CONFIG = {"max_retries": 3, "retry_delay": 1}


# ========== 2. 数据持久化 ==========

def save_data():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({
            "next_id": next_id,
            "persons": persons,
            "pending_reviews": pending_reviews,
            "process_instances": process_instances,
            "reminders": reminders  # 👈 新增
        }, f, ensure_ascii=False, indent=2)


def load_data():
    global next_id, persons, pending_reviews, process_instances, reminders
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            next_id = data.get("next_id", 1)
            persons = {int(k): v for k, v in data.get("persons", {}).items()}
            pending_reviews = data.get("pending_reviews", [])
            process_instances = data.get("process_instances", {})
            reminders = data.get("reminders", [])  # 👈 新增
    except FileNotFoundError:
        pass


load_data()


# ========== 3. 提醒管理函数 👈 新增 ==========

def create_reminder(reminder_type: str, process_id: str, message: str, severity: str = "normal"):
    """创建提醒记录"""
    reminder = {
        "id": f"reminder_{len(reminders) + 1}",
        "type": reminder_type,
        "process_id": process_id,
        "message": message,
        "severity": severity,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",
        "acknowledged_by": None,
        "acknowledged_at": None
    }
    reminders.append(reminder)
    save_data()
    return reminder


def get_pending_reminders():
    """获取待处理的提醒"""
    return [r for r in reminders if r["status"] == "pending"]


def acknowledge_reminder(reminder_id: str, user_id: str = "system"):
    """确认已查看提醒"""
    for reminder in reminders:
        if reminder["id"] == reminder_id:
            reminder["status"] = "acknowledged"
            reminder["acknowledged_by"] = user_id
            reminder["acknowledged_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            save_data()
            return reminder
    return None


# ========== 4. 审核系统 ==========

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


# ========== 5. 流程管理 ==========

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


# ========== 6. 任务执行 ==========

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
            "message": "✅ 已创建人员档案"
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


# ========== 7. 监控检测函数 👈 新增 ==========

def calculate_duration_minutes(start_time_str: str) -> int:
    """计算时间差（分钟）"""
    try:
        start_time = time.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        start_timestamp = time.mktime(start_time)
        current_timestamp = time.time()
        duration_seconds = current_timestamp - start_timestamp
        return int(duration_seconds / 60)
    except:
        return 0


def check_review_timeout():
    """检查审核超时"""
    timeout_threshold = MONITOR_CONFIG["review_timeout"] / 60
    timeout_reviews = []

    for review in pending_reviews:
        if review["status"] != "pending":
            continue

        duration = calculate_duration_minutes(review["created_at"])

        if duration > timeout_threshold:
            related_process = None
            for proc in process_instances.values():
                if proc["status"] == "paused":
                    related_process = proc
                    break

            timeout_reviews.append({
                "review_id": review["id"],
                "operation": review["operation"],
                "duration_minutes": duration,
                "process_id": related_process["id"] if related_process else None,
                "person_name": related_process["person_data"]["name"] if related_process else "未知"
            })

    return timeout_reviews


def check_process_timeout():
    """检查流程执行超时"""
    timeout_threshold = MONITOR_CONFIG["process_timeout"] / 60
    timeout_processes = []

    for proc in process_instances.values():
        if proc["status"] not in ["running", "paused"]:
            continue

        duration = calculate_duration_minutes(proc["created_at"])

        if duration > timeout_threshold:
            timeout_processes.append({
                "process_id": proc["id"],
                "person_name": proc["person_data"]["name"],
                "duration_minutes": duration,
                "current_step": proc["current_step"],
                "total_steps": len(proc["tasks"]),
                "status": proc["status"]
            })

    return timeout_processes


def check_failed_processes():
    """检查失败的流程"""
    failed_processes = []

    for proc in process_instances.values():
        if proc["status"] == "failed":
            existing_reminder = any(
                r["process_id"] == proc["id"] and r["type"] == "process_failed"
                for r in reminders
            )

            if not existing_reminder:
                failed_processes.append({
                    "process_id": proc["id"],
                    "person_name": proc["person_data"]["name"],
                    "error": proc.get("error", "未知错误"),
                    "failed_at": proc["updated_at"]
                })

    return failed_processes


def analyze_process_health():
    """分析整体流程健康度"""
    total = len(process_instances)
    if total == 0:
        return {
            "total": 0,
            "health_score": 100,
            "status": "excellent"
        }

    running = len([p for p in process_instances.values() if p["status"] == "running"])
    paused = len([p for p in process_instances.values() if p["status"] == "paused"])
    failed = len([p for p in process_instances.values() if p["status"] == "failed"])
    completed = len([p for p in process_instances.values() if p["status"] == "completed"])

    health_score = (completed * 100 + running * 80 + paused * 50 + failed * 0) / total if total > 0 else 100

    if health_score >= 90:
        status = "excellent"
    elif health_score >= 70:
        status = "good"
    elif health_score >= 50:
        status = "warning"
    else:
        status = "critical"

    return {
        "total": total,
        "running": running,
        "paused": paused,
        "failed": failed,
        "completed": completed,
        "health_score": int(health_score),
        "status": status,
        "pending_reviews": len(get_pending_reviews()),
        "pending_reminders": len(get_pending_reminders())
    }


# ========== 8. AI 工具函数 ==========

# 原有工具
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


# 👈 新增：监控工具
def monitor_system_tool() -> str:
    """AI 调用此工具进行系统监控"""
    report_lines = ["📊 系统监控报告", "=" * 50, ""]

    # 整体健康度
    health = analyze_process_health()

    status_emoji = {
        "excellent": "✅",
        "good": "🟢",
        "warning": "⚠️",
        "critical": "🔴"
    }

    report_lines.append(f"🏥 系统健康度: {health['health_score']}/100 {status_emoji[health['status']]}")
    report_lines.append(f"📈 流程统计:")
    report_lines.append(f"   - 总计: {health['total']}")
    report_lines.append(f"   - 运行中: {health['running']}")
    report_lines.append(f"   - 暂停: {health['paused']}")
    report_lines.append(f"   - 失败: {health['failed']}")
    report_lines.append(f"   - 完成: {health['completed']}")
    report_lines.append(f"   - 待审核: {health['pending_reviews']}")
    report_lines.append("")

    # 检查审核超时
    timeout_reviews = check_review_timeout()
    if timeout_reviews:
        report_lines.append(f"⚠️ 发现 {len(timeout_reviews)} 个审核超时:")
        for item in timeout_reviews:
            report_lines.append(
                f"   - {item['person_name']} 的 {item['operation']} "
                f"已等待 {item['duration_minutes']} 分钟 (审核ID: {item['review_id']})"
            )

            # 检查是否已创建提醒
            existing = any(
                r["type"] == "review_timeout" and r["process_id"] == item["process_id"]
                for r in reminders
            )

            if not existing:
                create_reminder(
                    reminder_type="review_timeout",
                    process_id=item["process_id"] or "unknown",
                    message=f"{item['person_name']} 的审核已等待 {item['duration_minutes']} 分钟",
                    severity="high" if item['duration_minutes'] > 180 else "normal"
                )
        report_lines.append("")

    # 检查流程超时
    timeout_processes = check_process_timeout()
    if timeout_processes:
        report_lines.append(f"⚠️ 发现 {len(timeout_processes)} 个流程执行超时:")
        for item in timeout_processes:
            report_lines.append(
                f"   - {item['person_name']} 的流程已执行 {item['duration_minutes']} 分钟"
            )
        report_lines.append("")

    # 检查失败流程
    failed_processes = check_failed_processes()
    if failed_processes:
        report_lines.append(f"🔴 发现 {len(failed_processes)} 个流程失败:")
        for item in failed_processes:
            report_lines.append(f"   - {item['person_name']}: {item['error']}")

            create_reminder(
                reminder_type="process_failed",
                process_id=item["process_id"],
                message=f"{item['person_name']} 的流程失败: {item['error']}",
                severity="critical"
            )
        report_lines.append("")

    # 总结
    if not timeout_reviews and not timeout_processes and not failed_processes:
        report_lines.append("✅ 所有流程运行正常，无异常情况")
    else:
        total_issues = len(timeout_reviews) + len(timeout_processes) + len(failed_processes)
        report_lines.append(f"📌 共发现 {total_issues} 个需要关注的问题")

    report_lines.append("")
    report_lines.append("=" * 50)
    report_lines.append(f"🕐 监控时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(report_lines)


def get_reminders_tool() -> str:
    """获取待处理的提醒"""
    pending = get_pending_reminders()

    if not pending:
        return "✅ 当前没有待处理的提醒"

    lines = [f"📬 待处理提醒 ({len(pending)} 条)", "=" * 50, ""]

    critical = [r for r in pending if r["severity"] == "critical"]
    high = [r for r in pending if r["severity"] == "high"]
    normal = [r for r in pending if r["severity"] == "normal"]

    if critical:
        lines.append("🔴 紧急提醒:")
        for r in critical:
            lines.append(f"   [{r['id']}] {r['message']}")
        lines.append("")

    if high:
        lines.append("⚠️ 重要提醒:")
        for r in high:
            lines.append(f"   [{r['id']}] {r['message']}")
        lines.append("")

    if normal:
        lines.append("ℹ️ 一般提醒:")
        for r in normal:
            lines.append(f"   [{r['id']}] {r['message']}")

    return "\n".join(lines)


def acknowledge_reminder_tool(reminder_id: str) -> str:
    """确认已查看提醒"""
    reminder = acknowledge_reminder(reminder_id)
    if not reminder:
        return f"❌ 提醒不存在：{reminder_id}"

    return f"✅ 已确认提醒: {reminder['message']}"


# ========== 9. 工具列表整合 ==========

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
    ),
    StructuredTool.from_function(
        func=monitor_system_tool,
        name="monitor_system",
        description="""监控系统状态。检查审核超时、流程超时、失败流程。
        AI应该在用户每次打招呼或询问系统状态时主动调用此工具。"""
    ),
    StructuredTool.from_function(
        func=get_reminders_tool,
        name="get_reminders",
        description="获取所有待处理的提醒"
    ),
    StructuredTool.from_function(
        func=acknowledge_reminder_tool,
        name="acknowledge_reminder",
        description="确认已查看提醒，需要提供reminder_id"
    )
]

# ========== 10. Agent 配置 ==========

llm = ChatOpenAI(
    api_key="sk-eyy7q4sejyOBK9FgbxjfHVmcPiw3ttLXR05FTMMilK9gFGFB",
    base_url="https://api.moonshot.cn/v1",
    model="moonshot-v1-8k",
    temperature=0
)

AGENT_SYSTEM_PROMPT = """你是企业业务流程助理，负责管理和监控业务流程。

核心能力：
1. 启动业务流程（入职、离职）
2. 查询流程状态
3. 批准审核任务
4. 主动监控系统状态
5. 管理提醒和告警

主动监控策略：
- 每次用户开始对话时（打招呼、询问状态等），先调用 monitor_system 检查系统
- 如果发现异常，主动告知用户
- 如果有待处理的提醒，主动提醒用户

工作流程示例：
用户："早上好" 或 "你好"
→ 先调用 monitor_system
→ 如果有问题："早上好！发现2个审核已超时，需要您处理..."
→ 如果正常："早上好！系统运行正常，有什么可以帮您？"

用户："帮张三办理入职，28岁，技术部"
→ 调用 start_process 工具

用户："有什么需要处理的"
→ 调用 get_reminders

重要规则：
- 入职流程需要：姓名、年龄、部门
- 缺少参数时主动询问
- 用友好、专业的语气
- 发现问题时要清晰说明严重程度
- 简洁回复，不要过于冗长"""

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

# ========== 11. FastAPI 应用 ==========

app = FastAPI()


def success(data=None, msg="ok"):
    return {"code": 0, "msg": msg, "data": data}


def error(msg="error", code=1):
    return {"code": code, "msg": msg, "data": None}


@app.get("/")
def root():
    return {
        "message": "DAY 17 AI 流程监控系统",
        "features": ["对话式操作", "主动监控", "智能提醒"]
    }


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


# 👈 新增：监控接口
@app.get("/api/monitor/health")
def get_system_health():
    """获取系统健康度"""
    health = analyze_process_health()
    return success(health)


@app.get("/api/monitor/report")
def get_monitor_report():
    """获取完整监控报告"""
    report = monitor_system_tool()
    return success({"report": report})


@app.get("/api/reminders")
def list_reminders():
    """获取所有提醒"""
    return success({
        "pending": get_pending_reminders(),
        "total": len(reminders)
    })


@app.post("/api/reminders/{reminder_id}/acknowledge")
def acknowledge_reminder_api(reminder_id: str):
    """确认提醒"""
    reminder = acknowledge_reminder(reminder_id)
    if not reminder:
        return error("提醒不存在")
    return success(reminder)


@app.get("/api/reviews")
def list_reviews():
    """查看待审核任务"""
    return success(get_pending_reviews())


# ========== 12. 启动服务 ==========

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("🚀 DAY 17 AI 流程监控系统")
    print("=" * 60)
    print("✨ 新功能：")
    print("  - ✅ AI 主动监控流程状态")
    print("  - ✅ 自动检测审核超时")
    print("  - ✅ 智能提醒和告警")
    print("  - ✅ 系统健康度评分")
    print("=" * 60)
    print("📖 API 文档：http://localhost:8000/docs")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)