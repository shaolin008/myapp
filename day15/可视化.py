from fastapi import FastAPI
import json
import time
from pydantic import BaseModel

# ========== 1. 全局数据存储 ==========

persons = {}
next_id = 1
pending_reviews = []
process_instances = {}  # 👈 改为字典，支持多个流程

# 任务清单定义
ONBOARDING_TASKS = [
    {"name": "添加人员档案", "need_review": False},
    {"name": "分配工号", "need_review": False},
    {"name": "创建系统账号", "need_review": True},
    {"name": "分配部门权限", "need_review": True},
    {"name": "发送欢迎邮件", "need_review": False}
]

# 重试配置
RETRY_CONFIG = {
    "max_retries": 3,
    "retry_delay": 1
}


# ========== 2. 数据持久化 ==========

def save_data():
    """保存数据到文件"""
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({
            "next_id": next_id,
            "persons": persons,
            "pending_reviews": pending_reviews,
            "process_instances": process_instances
        }, f, ensure_ascii=False, indent=2)


def load_data():
    """从文件加载数据"""
    global next_id, persons, pending_reviews, process_instances
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            next_id = data.get("next_id", 1)
            persons = {int(k): v for k, v in data.get("persons", {}).items()}
            pending_reviews = data.get("pending_reviews", [])
            process_instances = data.get("process_instances", {})
    except FileNotFoundError:
        print("数据文件不存在，使用默认值")


load_data()


# ========== 3. 审核系统 ==========

def create_review_task(operation: str, params: dict, ai_analysis: str):
    """创建审核任务"""
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


# ========== 4. 流程管理（升级版）==========

def create_process(name: str, age: int, department: str):
    """创建流程实例"""
    process_id = f"proc_{len(process_instances) + 1}_{int(time.time())}"

    process = {
        "id": process_id,
        "person_data": {
            "name": name,
            "age": age,
            "department": department
        },
        "tasks": [t.copy() for t in ONBOARDING_TASKS],  # 深拷贝
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
    """更新流程"""
    if process_id in process_instances:
        if updates:
            process_instances[process_id].update(updates)
        process_instances[process_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_data()
        return process_instances[process_id]
    return None


def visualize_process(process):
    """流程可视化"""
    steps = process["tasks"]
    current = process["current_step"]

    progress_bar = ""
    step_details = []

    for i, task in enumerate(steps):
        task_name = task["name"]

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
            "name": task_name,
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


# ========== 5. 补偿机制 ==========

def compensate_add_person(person_id: int):
    """补偿：删除人员"""
    if person_id in persons:
        del persons[person_id]
        save_data()
        return {"success": True, "message": f"已删除人员 {person_id}"}
    return {"success": False, "message": "人员不存在"}


def compensate_assign_employee_number(employee_number: str):
    """补偿：回收工号"""
    return {"success": True, "message": f"已回收工号 {employee_number}"}


COMPENSATION_HANDLERS = {
    "添加人员档案": compensate_add_person,
    "分配工号": compensate_assign_employee_number
}


def rollback_process(process_id: str):
    """回滚流程"""
    process = get_process(process_id)
    if not process:
        return {"error": "流程不存在"}

    compensation_log = []

    for result in reversed(process["results"]):
        task_name = result["task_name"]

        if task_name in COMPENSATION_HANDLERS:
            handler = COMPENSATION_HANDLERS[task_name]

            if task_name == "添加人员档案":
                person_id = result["data"]["person_id"]
                comp_result = handler(person_id)
            elif task_name == "分配工号":
                employee_number = result["data"]["employee_number"]
                comp_result = handler(employee_number)
            else:
                comp_result = {"success": True}

            compensation_log.append({
                "task": task_name,
                "compensation": comp_result
            })

    process["status"] = "rolled_back"
    process["compensation_log"] = compensation_log
    update_process(process_id)

    return {
        "process_id": process_id,
        "status": "rolled_back",
        "message": "流程已回滚",
        "compensation_log": compensation_log
    }


# ========== 6. 任务执行（带错误处理）==========

def execute_with_retry(func, *args, **kwargs):
    """带重试的执行"""
    last_error = None

    for attempt in range(RETRY_CONFIG["max_retries"]):
        try:
            result = func(*args, **kwargs)
            if result.get("status") != "error":
                return result
            last_error = result.get("message", "未知错误")
        except Exception as e:
            last_error = str(e)
            print(f"⚠️ 尝试 {attempt + 1}/{RETRY_CONFIG['max_retries']}: {last_error}")

            if attempt < RETRY_CONFIG["max_retries"] - 1:
                time.sleep(RETRY_CONFIG["retry_delay"])

    return {
        "status": "error",
        "message": f"执行失败（已重试 {RETRY_CONFIG['max_retries']} 次）: {last_error}"
    }


def execute_task_directly(task_name: str, person_data: dict):
    """直接执行任务"""
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
            "message": f"✅ 已创建人员档案：{person_data['name']}"
        }

    elif task_name == "分配工号":
        employee_number = f"EMP{next_id:04d}"
        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"employee_number": employee_number},
            "message": f"✅ 已分配工号：{employee_number}"
        }

    elif task_name == "发送欢迎邮件":
        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"email_sent": True},
            "message": f"✅ 已发送欢迎邮件"
        }

    return {
        "task_name": task_name,
        "status": "completed",
        "data": {},
        "message": f"✅ 已完成：{task_name}"
    }


def execute_current_task(process):
    """执行当前任务（带错误处理）"""
    step_index = process["current_step"]
    task = process["tasks"][step_index]
    task_name = task["name"]

    print(f"\n>>> 执行：{task_name}")

    try:
        if task["need_review"]:
            ai_analysis = f"""
流程审核：
- 步骤：{task_name}
- 人员：{process['person_data']['name']}
"""
            task_id = create_review_task(
                operation=task_name,
                params=process["person_data"],
                ai_analysis=ai_analysis
            )

            result = {
                "task_name": task_name,
                "status": "pending_review",
                "task_id": task_id,
                "message": f"⏸️ 需要审核"
            }
            process["results"].append(result)
            process["status"] = "paused"
            update_process(process["id"])

            return {
                "action": "pause",
                "message": f"任务'{task_name}'需要审核",
                "review_task_id": task_id
            }

        # 带重试执行
        result = execute_with_retry(
            execute_task_directly,
            task_name,
            process["person_data"]
        )

        if result.get("status") == "error":
            process["status"] = "failed"
            process["error"] = result["message"]
            update_process(process["id"])

            return {
                "action": "fail",
                "error": result["message"]
            }

        process["results"].append(result)
        process["current_step"] += 1
        update_process(process["id"])

        return {
            "action": "continue",
            "result": result
        }

    except Exception as e:
        error_msg = f"执行异常: {str(e)}"
        process["status"] = "failed"
        process["error"] = error_msg
        update_process(process["id"])

        return {
            "action": "fail",
            "error": error_msg
        }


# ========== 7. FastAPI 应用 ==========

app = FastAPI()


def success(data=None, msg="ok"):
    return {"code": 0, "msg": msg, "data": data}


def error(msg="error", code=1):
    return {"code": code, "msg": msg, "data": None}


# ========== 8. 基础接口 ==========

@app.get("/")
def root():
    return {
        "message": "DAY 15 流程管理系统（生产级）",
        "features": ["多流程并发", "可视化", "错误处理", "回滚机制"]
    }


@app.get("/persons")
def list_persons():
    return success(persons)


@app.get("/api/reviews")
def list_reviews():
    return success(get_pending_reviews())


@app.post("/api/reviews/{task_id}/approve")
def approve_task(task_id: str):
    task = approve_review(task_id)
    if not task:
        return error("任务不存在")
    return success({"message": "已批准", "task_id": task_id})


# ========== 9. 流程接口（升级版）==========

@app.post("/api/process/onboarding/start")
def start_onboarding(name: str, age: int, department: str):
    """启动入职流程"""
    print(f"\n{'=' * 50}")
    print(f"启动入职流程：{name}")
    print(f"{'=' * 50}")

    process = create_process(name, age, department)
    execution_log = []

    while process["current_step"] < len(process["tasks"]):
        result = execute_current_task(process)
        execution_log.append(result)

        if result["action"] == "pause":
            viz = visualize_process(process)
            return success({
                **viz,
                "review_task_id": result["review_task_id"],
                "execution_log": execution_log
            })

        if result["action"] == "fail":
            viz = visualize_process(process)
            return success({
                **viz,
                "execution_log": execution_log
            })

    process["status"] = "completed"
    update_process(process["id"])
    viz = visualize_process(process)

    return success({
        **viz,
        "execution_log": execution_log
    })


@app.get("/api/process/{proc_id}")
def get_process_status(proc_id: str):
    """查看流程状态（可视化）"""
    process = get_process(proc_id)
    if not process:
        return error("流程不存在")

    viz = visualize_process(process)
    return success(viz)


@app.get("/api/processes")
def list_processes():
    """列出所有流程"""
    processes = []
    for proc_id, proc in process_instances.items():
        viz = visualize_process(proc)
        processes.append(viz)
    return success(processes)


@app.post("/api/process/{proc_id}/continue")
def continue_process(proc_id: str):
    """继续执行流程"""
    process = get_process(proc_id)

    if not process:
        return error("流程不存在")

    if process["status"] != "paused":
        return error("流程不在暂停状态")

    print(f"\n{'=' * 50}")
    print(f"继续执行流程：{proc_id}")
    print(f"{'=' * 50}")

    process["current_step"] += 1
    process["status"] = "running"
    update_process(proc_id)

    execution_log = []

    while process["current_step"] < len(process["tasks"]):
        result = execute_current_task(process)
        execution_log.append(result)

        if result["action"] == "pause":
            viz = visualize_process(process)
            return success({
                **viz,
                "review_task_id": result["review_task_id"],
                "execution_log": execution_log
            })

        if result["action"] == "fail":
            viz = visualize_process(process)
            return success({
                **viz,
                "execution_log": execution_log
            })

    process["status"] = "completed"
    update_process(proc_id)
    viz = visualize_process(process)

    return success({
        **viz,
        "execution_log": execution_log
    })


@app.post("/api/process/{proc_id}/rollback")
def rollback_process_api(proc_id: str):
    """回滚流程"""
    result = rollback_process(proc_id)
    if "error" in result:
        return error(result["error"])
    return success(result)


# ========== 10. 启动服务 ==========

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("🚀 DAY 15 流程管理系统（生产级）启动中...")
    print("=" * 60)
    print("✨ 新功能：")
    print("  - ✅ 多流程并发管理")
    print("  - ✅ 流程可视化")
    print("  - ✅ 自动错误处理和重试")
    print("  - ✅ 流程回滚机制")
    print("=" * 60)
    print("📖 API 文档：http://localhost:8000/docs")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)