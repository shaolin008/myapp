from fastapi import FastAPI
import json
from pydantic import BaseModel

# ========== 1. 全局数据存储 ==========

persons = {}
next_id = 1
pending_reviews = []

# 流程实例存储
process_storage = {
    "current_process": None
}

# 任务清单定义
ONBOARDING_TASKS = [
    {"name": "添加人员档案", "need_review": False},
    {"name": "分配工号", "need_review": False},
    {"name": "创建系统账号", "need_review": True},  # 需要审核
    {"name": "分配部门权限", "need_review": True},  # 需要审核
    {"name": "发送欢迎邮件", "need_review": False}
]


# ========== 2. 数据持久化函数 ==========

def save_data():
    """保存数据到文件"""
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({
            "next_id": next_id,
            "persons": persons,
            "pending_reviews": pending_reviews
        }, f, ensure_ascii=False, indent=2)


def load_data():
    """从文件加载数据"""
    global next_id, persons, pending_reviews
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            next_id = data.get("next_id", 1)
            persons = {int(k): v for k, v in data.get("persons", {}).items()}
            pending_reviews = data.get("pending_reviews", [])
    except FileNotFoundError:
        print("数据文件不存在，使用默认值")


# 启动时加载数据
load_data()


# ========== 3. 审核系统函数 ==========

def create_review_task(operation: str, params: dict, ai_analysis: str):
    """创建审核任务"""
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
    """获取待审核任务"""
    return [t for t in pending_reviews if t["status"] == "pending"]


def approve_review(task_id: str):
    """批准审核任务"""
    for task in pending_reviews:
        if task["id"] == task_id:
            task["status"] = "approved"
            save_data()
            return task
    return None


# ========== 4. 流程管理函数 ==========

def create_process(name: str, age: int, department: str):
    """创建一个新的流程实例"""
    process_storage["current_process"] = {
        "id": "proc_001",
        "person_data": {
            "name": name,
            "age": age,
            "department": department
        },
        "tasks": ONBOARDING_TASKS,
        "current_step": 0,
        "status": "running",
        "results": []
    }
    return process_storage["current_process"]


def get_current_process():
    """获取当前流程"""
    return process_storage["current_process"]


def execute_task_directly(task_name: str, person_data: dict):
    """直接执行任务（不需要审核的）"""
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
    """执行当前任务"""
    step_index = process["current_step"]
    task = process["tasks"][step_index]
    task_name = task["name"]

    print(f"\n>>> 正在执行：{task_name}")

    # 判断是否需要审核
    if task["need_review"]:
        ai_analysis = f"""
流程审核请求：
- 流程：员工入职
- 步骤：{task_name}
- 人员：{process['person_data']['name']}
- 部门：{process['person_data']['department']}
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
            "message": f"⏸️ 任务'{task_name}'需要审核"
        }
        process["results"].append(result)
        process["status"] = "paused"

        return {
            "action": "pause",
            "message": f"任务'{task_name}'需要审核，流程已暂停",
            "review_task_id": task_id
        }

    # 不需要审核，直接执行
    result = execute_task_directly(task_name, process["person_data"])
    process["results"].append(result)
    process["current_step"] += 1

    return {
        "action": "continue",
        "result": result
    }


# ========== 5. FastAPI 应用 ==========

app = FastAPI()


def success(data=None, msg="ok"):
    return {"code": 0, "msg": msg, "data": data}


def error(msg="error", code=1):
    return {"code": code, "msg": msg, "data": None}


# ========== 6. 基础接口 ==========

@app.get("/")
def root():
    return {"message": "DAY 14 流程管理系统"}


@app.get("/persons")
def list_persons():
    """查看所有人员"""
    return success(persons)


@app.get("/api/reviews")
def list_reviews():
    """查看待审核任务"""
    return success(get_pending_reviews())


@app.post("/api/reviews/{task_id}/approve")
def approve_task(task_id: str):
    """批准审核任务"""
    task = approve_review(task_id)
    if not task:
        return error("任务不存在")
    return success({
        "message": "任务已批准",
        "task_id": task_id
    })


# ========== 7. 流程接口（核心）==========

@app.post("/api/process/onboarding/start")
def start_onboarding(name: str, age: int, department: str):
    """开始员工入职流程"""
    print(f"\n{'=' * 50}")
    print(f"开始入职流程：{name}")
    print(f"{'=' * 50}")

    # 创建流程实例
    process = create_process(name, age, department)

    # 开始执行任务
    execution_log = []

    while process["current_step"] < len(process["tasks"]):
        result = execute_current_task(process)
        execution_log.append(result)

        # 如果遇到需要暂停的
        if result["action"] == "pause":
            print(f"\n⏸️ 流程暂停在步骤 {process['current_step'] + 1}")
            return success({
                "process_id": process["id"],
                "status": "paused",
                "message": result["message"],
                "review_task_id": result["review_task_id"],
                "completed_steps": process["current_step"],
                "total_steps": len(process["tasks"]),
                "execution_log": execution_log,
                "next_action": f"请批准审核任务：{result['review_task_id']}"
            })

    # 全部完成
    process["status"] = "completed"
    print(f"\n✅ 流程全部完成！")
    return success({
        "process_id": process["id"],
        "status": "completed",
        "message": "入职流程全部完成",
        "results": process["results"]
    })


@app.get("/api/process/current")
def get_process_status():
    """查看当前流程状态"""
    process = get_current_process()
    if not process:
        return error("没有正在执行的流程")
    return success(process)


@app.post("/api/process/onboarding/continue")
def continue_onboarding():
    """继续执行暂停的流程"""
    process = get_current_process()

    if not process:
        return error("没有正在执行的流程")

    if process["status"] != "paused":
        return error("流程不在暂停状态")

    print(f"\n{'=' * 50}")
    print(f"继续执行流程...")
    print(f"{'=' * 50}")

    # 跳过当前需要审核的步骤
    process["current_step"] += 1
    process["status"] = "running"

    # 继续执行剩余任务
    execution_log = []

    while process["current_step"] < len(process["tasks"]):
        result = execute_current_task(process)
        execution_log.append(result)

        if result["action"] == "pause":
            print(f"\n⏸️ 流程再次暂停在步骤 {process['current_step'] + 1}")
            return success({
                "process_id": process["id"],
                "status": "paused",
                "message": result["message"],
                "review_task_id": result["review_task_id"],
                "execution_log": execution_log
            })

    # 全部完成
    process["status"] = "completed"
    print(f"\n✅ 流程全部完成！")
    return success({
        "process_id": process["id"],
        "status": "completed",
        "message": "入职流程全部完成",
        "results": process["results"]
    })


# ========== 8. 启动服务 ==========

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 50)
    print("🚀 DAY 14 流程管理系统启动中...")
    print("=" * 50)
    print("📖 API 文档：http://localhost:8000/docs")
    print("=" * 50 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)