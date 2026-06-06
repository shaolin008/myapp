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

customers = {}  # 客户数据
next_customer_id = 1
followup_records = []  # 跟进记录
process_instances = {}
pending_reviews = []
reminders = []
review_history = []

# 销售团队
sales_team = {
    "sales_001": {
        "id": "sales_001",
        "name": "李明",
        "region": "北京",
        "industries": ["互联网", "金融"],
        "active_customers": 0,
        "total_closed": 0
    },
    "sales_002": {
        "id": "sales_002",
        "name": "王芳",
        "region": "上海",
        "industries": ["教育", "医疗"],
        "active_customers": 0,
        "total_closed": 0
    },
    "sales_003": {
        "id": "sales_003",
        "name": "赵强",
        "region": "深圳",
        "industries": ["制造业", "互联网"],
        "active_customers": 0,
        "total_closed": 0
    }
}

# 客户录入流程
CUSTOMER_ONBOARDING_TASKS = [
    {"name": "录入客户信息", "need_review": False},
    {"name": "生成客户编号", "need_review": False},
    {"name": "分配销售负责人", "need_review": True},
    {"name": "设置跟进计划", "need_review": False},
    {"name": "发送通知", "need_review": False}
]

# 监控配置
MONITOR_CONFIG = {
    "check_interval": 600,
    "review_timeout": 300,
    "process_timeout": 14400,
    "enable_auto_reminder": True
}


# ========== 2. 数据持久化 ==========

def save_data():
    with open("crm_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "next_customer_id": next_customer_id,
            "customers": customers,
            "followup_records": followup_records,
            "process_instances": process_instances,
            "pending_reviews": pending_reviews,
            "reminders": reminders,
            "review_history": review_history,
            "sales_team": sales_team
        }, f, ensure_ascii=False, indent=2)


def load_data():
    global next_customer_id, customers, followup_records, process_instances
    global pending_reviews, reminders, review_history, sales_team

    try:
        with open("crm_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            next_customer_id = data.get("next_customer_id", 1)
            customers = data.get("customers", {})
            followup_records = data.get("followup_records", [])
            process_instances = data.get("process_instances", {})
            pending_reviews = data.get("pending_reviews", [])
            reminders = data.get("reminders", [])
            review_history = data.get("review_history", [])

            # 合并销售团队数据（保留默认值）
            loaded_sales = data.get("sales_team", {})
            for sales_id, sales_data in loaded_sales.items():
                if sales_id in sales_team:
                    sales_team[sales_id].update(sales_data)
    except FileNotFoundError:
        pass


load_data()


# ========== 3. 客户管理核心函数 ==========

def generate_customer_id():
    """生成客户编号：CUS + 日期 + 序号"""
    global next_customer_id
    date_str = time.strftime("%Y%m%d")
    customer_id = f"CUS{date_str}{next_customer_id:03d}"
    next_customer_id += 1
    return customer_id


def recommend_sales_person(customer_data: dict) -> dict:
    """AI 推荐销售负责人"""
    industry = customer_data.get("industry", "")
    region = customer_data.get("region", "")

    scores = {}

    for sales_id, sales in sales_team.items():
        score = 0
        reasons = []

        # 因素 1：行业匹配（30分）
        if industry in sales.get("industries", []):
            score += 30
            reasons.append(f"擅长{industry}行业")

        # 因素 2：地区匹配（20分）
        if region == sales.get("region", ""):
            score += 20
            reasons.append(f"负责{region}地区")

        # 因素 3：负载均衡（30分）
        active = sales.get("active_customers", 0)
        if active < 5:
            score += 30
            reasons.append(f"当前客户数较少（{active}个）")
        elif active < 10:
            score += 15
            reasons.append(f"当前客户数适中（{active}个）")
        else:
            score += 5
            reasons.append(f"当前客户数较多（{active}个）")

        # 因素 4：历史成交（20分）
        total_closed = sales.get("total_closed", 0)
        if total_closed > 10:
            score += 20
            reasons.append(f"历史成交{total_closed}个")
        elif total_closed > 5:
            score += 10
            reasons.append(f"历史成交{total_closed}个")

        scores[sales_id] = {
            "sales_id": sales_id,
            "name": sales["name"],
            "score": score,
            "reasons": reasons
        }

    # 按分数排序
    recommended = sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    return {
        "recommended": recommended[0] if recommended else None,
        "all_options": recommended
    }


def create_customer_onboarding_process(customer_data: dict):
    """创建客户录入流程"""
    process_id = f"cust_{len(process_instances) + 1}_{int(time.time())}"
    process = {
        "id": process_id,
        "customer_data": customer_data,
        "tasks": [t.copy() for t in CUSTOMER_ONBOARDING_TASKS],
        "current_step": 0,
        "status": "running",
        "results": [],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "error": None,
        "customer_id": None
    }
    process_instances[process_id] = process
    save_data()
    return process


def execute_customer_task(task_name: str, customer_data: dict, process: dict):
    """执行客户录入任务"""

    if task_name == "录入客户信息":
        required = ["name", "contact_person", "phone", "industry", "source"]
        for field in required:
            if field not in customer_data or not customer_data[field]:
                return {
                    "task_name": task_name,
                    "status": "error",
                    "message": f"❌ 缺少必需字段：{field}"
                }

        return {
            "task_name": task_name,
            "status": "completed",
            "data": customer_data,
            "message": f"✅ 已录入客户：{customer_data['name']}"
        }

    elif task_name == "生成客户编号":
        customer_id = generate_customer_id()
        process["customer_id"] = customer_id

        customers[customer_id] = {
            "customer_id": customer_id,
            **customer_data,
            "status": "potential",
            "assigned_to": None,
            "created_at": time.strftime("%Y-%m-%d"),
            "last_contact": time.strftime("%Y-%m-%d"),
            "next_followup": None,
            "followup_count": 0
        }
        save_data()

        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"customer_id": customer_id},
            "message": f"✅ 已生成客户编号：{customer_id}"
        }

    elif task_name == "分配销售负责人":
        assigned_to = customer_data.get("assigned_to", "待分配")

        # 更新客户和销售数据
        customer_id = process.get("customer_id")
        if customer_id and customer_id in customers:
            customers[customer_id]["assigned_to"] = assigned_to

            # 更新销售的客户数
            if assigned_to in sales_team:
                sales_team[assigned_to]["active_customers"] += 1

            save_data()

        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"assigned_to": assigned_to},
            "message": f"✅ 已分配销售负责人：{assigned_to}"
        }

    elif task_name == "设置跟进计划":
        next_followup = time.strftime(
            "%Y-%m-%d",
            time.localtime(time.time() + 3 * 86400)
        )

        customer_id = process.get("customer_id")
        if customer_id and customer_id in customers:
            customers[customer_id]["next_followup"] = next_followup
            save_data()

        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"next_followup": next_followup},
            "message": f"✅ 已设置跟进计划：{next_followup}"
        }

    elif task_name == "发送通知":
        return {
            "task_name": task_name,
            "status": "completed",
            "data": {"notification_sent": True},
            "message": f"✅ 已发送通知"
        }

    return {
        "task_name": task_name,
        "status": "completed",
        "data": {},
        "message": f"✅ 已完成：{task_name}"
    }


# ========== 4. 审核系统（复用之前的代码）==========

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


def record_review_decision(review_id: str, decision: str, decided_by: str = "system"):
    review_task = None
    for review in pending_reviews:
        if review["id"] == review_id:
            review_task = review
            break

    if not review_task:
        return None

    history_record = {
        "review_id": review_id,
        "operation": review_task["operation"],
        "params": review_task["params"],
        "decision": decision,
        "decided_by": decided_by,
        "decided_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "wait_duration": calculate_duration_minutes(review_task["created_at"])
    }

    review_history.append(history_record)
    save_data()
    return history_record


# ========== 5. 流程管理（复用）==========

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

    for i, task in enumerate(steps):
        if i < current:
            icon = "✅"
        elif i == current:
            if process["status"] == "paused":
                icon = "⏸️"
            elif process["status"] == "failed":
                icon = "❌"
            else:
                icon = "▶️"
        else:
            icon = "⏳"

        progress_bar += f"{icon} "

    progress_percent = int((current / len(steps)) * 100) if steps else 0

    return {
        "process_id": process["id"],
        "progress_bar": progress_bar.strip(),
        "progress_percent": progress_percent,
        "current_step": current + 1,
        "total_steps": len(steps),
        "status": process["status"]
    }


# ========== 6. 监控函数（复用）==========

def calculate_duration_minutes(start_time_str: str) -> int:
    try:
        start_time = time.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        start_timestamp = time.mktime(start_time)
        current_timestamp = time.time()
        duration_seconds = current_timestamp - start_timestamp
        return int(duration_seconds / 60)
    except:
        return 0


def create_reminder(reminder_type: str, process_id: str, message: str, severity: str = "normal"):
    reminder = {
        "id": f"reminder_{len(reminders) + 1}",
        "type": reminder_type,
        "process_id": process_id,
        "message": message,
        "severity": severity,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending"
    }
    reminders.append(reminder)
    save_data()
    return reminder


def get_pending_reminders():
    return [r for r in reminders if r["status"] == "pending"]


def check_review_timeout():
    timeout_threshold = MONITOR_CONFIG["review_timeout"] / 60
    timeout_reviews = []

    for review in pending_reviews:
        if review["status"] != "pending":
            continue

        duration = calculate_duration_minutes(review["created_at"])

        if duration > timeout_threshold:
            timeout_reviews.append({
                "review_id": review["id"],
                "operation": review["operation"],
                "duration_minutes": duration
            })

    return timeout_reviews


def assess_review_risk(review_id: str) -> dict:
    review_task = None
    for review in pending_reviews:
        if review["id"] == review_id:
            review_task = review
            break

    if not review_task:
        return {"error": "审核任务不存在"}

    risk_score = 20  # 基础分数
    risk_factors = []

    wait_duration = calculate_duration_minutes(review_task["created_at"])
    if wait_duration < 30:
        risk_score += 10
        risk_factors.append("审核刚创建，建议仔细审查")

    risk_score = max(0, min(100, risk_score))

    if risk_score < 30:
        risk_level = "low"
        risk_emoji = "🟢"
        risk_label = "低风险"
        recommendation = "approve"
        recommendation_text = "✅ 建议批准"
    elif risk_score < 60:
        risk_level = "medium"
        risk_emoji = "🟡"
        risk_label = "中风险"
        recommendation = "review"
        recommendation_text = "⚠️ 建议人工审查"
    else:
        risk_level = "high"
        risk_emoji = "🔴"
        risk_label = "高风险"
        recommendation = "reject"
        recommendation_text = "❌ 建议拒绝"

    return {
        "review_id": review_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_emoji": risk_emoji,
        "risk_label": risk_label,
        "risk_factors": risk_factors,
        "recommendation": recommendation,
        "recommendation_text": recommendation_text
    }


# ========== 7. AI 工具函数 ==========

def add_customer_tool(
        name: str,
        contact_person: str,
        phone: str,
        industry: str,
        source: str,
        region: str = "未知",
        email: str = "",
        assigned_to: str = ""
) -> str:
    """添加客户并启动录入流程"""

    customer_data = {
        "name": name,
        "contact_person": contact_person,
        "phone": phone,
        "email": email,
        "industry": industry,
        "source": source,
        "region": region
    }

    # AI 推荐销售
    recommendation = None
    if not assigned_to:
        recommendation = recommend_sales_person(customer_data)
        if recommendation["recommended"]:
            rec = recommendation["recommended"]
            customer_data["assigned_to"] = rec["sales_id"]
            customer_data["assignment_reason"] = "，".join(rec["reasons"])
        else:
            customer_data["assigned_to"] = "待分配"
    else:
        customer_data["assigned_to"] = assigned_to

    # 创建流程
    process = create_customer_onboarding_process(customer_data)

    # 执行流程
    while process["current_step"] < len(process["tasks"]):
        task = process["tasks"][process["current_step"]]
        task_name = task["name"]

        if task["need_review"]:
            if assigned_to:
                ai_analysis = f"客户录入审核：{task_name}\n客户：{name}\n指定负责人：{assigned_to}"
            else:
                rec = recommendation["recommended"]
                ai_analysis = f"""客户录入审核：{task_name}
客户：{name}（{industry}，{region}）
AI 推荐负责人：{rec['name']} ({rec['sales_id']})
推荐理由：{', '.join(rec['reasons'])}
推荐评分：{rec['score']}/100"""

            task_id = create_review_task(
                operation=task_name,
                params=customer_data,
                ai_analysis=ai_analysis
            )

            result = {
                "task_name": task_name,
                "status": "pending_review",
                "task_id": task_id
            }
            process["results"].append(result)
            process["status"] = "paused"
            update_process(process["id"], process)

            viz = visualize_process(process)

            response = f"""✅ 已为客户 {name} 启动录入流程
客户编号：{process.get('customer_id', '待分配')}
联系人：{contact_person}
行业：{industry}
流程ID：{process['id']}
进度：{viz['progress_bar']}
完成度：{viz['progress_percent']}%

当前状态：等待审核 - {task_id}
审核项：{task_name}"""

            if not assigned_to and recommendation and recommendation["recommended"]:
                rec = recommendation["recommended"]
                response += f"\n\n💡 AI 推荐负责人：{rec['name']} ({rec['sales_id']})"
                response += f"\n推荐理由：{', '.join(rec['reasons'])}"
                response += f"\n推荐评分：{rec['score']}/100"

            return response

        result = execute_customer_task(task_name, customer_data, process)

        if result.get("status") == "error":
            process["status"] = "failed"
            process["error"] = result["message"]
            update_process(process["id"], process)
            return result["message"]

        process["results"].append(result)
        process["current_step"] += 1
        update_process(process["id"], process)

    process["status"] = "completed"
    update_process(process["id"], process)

    customer_id = process["customer_id"]
    return f"""✅ 客户 {name} 的录入流程已全部完成！
客户编号：{customer_id}
负责人：{customer_data.get('assigned_to', '未分配')}
下次跟进：{customers[customer_id].get('next_followup', '待设置')}"""


def query_customer_tool(customer_id: str = None, name: str = None) -> str:
    """查询客户信息"""
    if customer_id:
        if customer_id in customers:
            c = customers[customer_id]
            return f"""📋 客户详情
━━━━━━━━━━━━━━━━━━━━━━━━
客户编号：{c['customer_id']}
公司名称：{c['name']}
联系人：{c['contact_person']}
电话：{c['phone']}
邮箱：{c.get('email', '未填写')}
行业：{c['industry']}
地区：{c.get('region', '未知')}
来源：{c['source']}
状态：{c['status']}
负责人：{c.get('assigned_to', '未分配')}
创建日期：{c['created_at']}
最后联系：{c.get('last_contact', '无')}
下次跟进：{c.get('next_followup', '未设置')}
跟进次数：{c.get('followup_count', 0)}
━━━━━━━━━━━━━━━━━━━━━━━━"""
        else:
            return f"❌ 未找到客户编号：{customer_id}"

    elif name:
        found = [c for c in customers.values() if name.lower() in c['name'].lower()]

        if not found:
            return f"❌ 未找到包含'{name}'的客户"

        result = f"📋 找到 {len(found)} 个客户：\n\n"
        for c in found:
            result += f"{c['customer_id']} - {c['name']} ({c['industry']}) - 负责人：{c.get('assigned_to', '未分配')}\n"

        return result

    else:
        total = len(customers)
        by_status = {}
        for c in customers.values():
            status = c.get('status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1

        result = f"📊 客户统计\n总计：{total} 个客户\n\n按状态分布：\n"
        for status, count in by_status.items():
            result += f"  - {status}: {count}\n"

        return result


def check_followup_tool() -> str:
    """检查需要跟进的客户"""
    today = time.strftime("%Y-%m-%d")

    due_today = []
    overdue = []

    for customer in customers.values():
        next_followup = customer.get("next_followup")
        if not next_followup:
            continue

        if next_followup == today:
            due_today.append(customer)
        elif next_followup < today:
            days_overdue = int(
                (time.mktime(time.strptime(today, "%Y-%m-%d")) -
                 time.mktime(time.strptime(next_followup, "%Y-%m-%d"))) / 86400
            )
            customer["days_overdue"] = days_overdue
            overdue.append(customer)

    result = "📅 客户跟进提醒\n" + "=" * 40 + "\n\n"

    if overdue:
        result += f"🔴 逾期未跟进（{len(overdue)} 个）：\n"
        for c in sorted(overdue, key=lambda x: x.get("days_overdue", 0), reverse=True):
            result += f"  - {c['customer_id']} {c['name']} - 逾期 {c.get('days_overdue', 0)} 天 - 负责人：{c.get('assigned_to', '未分配')}\n"
        result += "\n"

    if due_today:
        result += f"⚠️ 今日应跟进（{len(due_today)} 个）：\n"
        for c in due_today:
            result += f"  - {c['customer_id']} {c['name']} - 负责人：{c.get('assigned_to', '未分配')}\n"
        result += "\n"

    if not overdue and not due_today:
        result += "✅ 暂无需要跟进的客户\n"

    return result


def sales_performance_tool() -> str:
    """销售业绩统计"""
    stats = {}

    for sales_id, sales in sales_team.items():
        stats[sales_id] = {
            "name": sales["name"],
            "total_customers": 0,
            "by_status": {}
        }

    stats["unassigned"] = {
        "name": "未分配",
        "total_customers": 0,
        "by_status": {}
    }

    for customer in customers.values():
        assigned = customer.get("assigned_to", "未分配")
        status = customer.get("status", "unknown")

        if assigned not in stats:
            assigned = "unassigned"

        stats[assigned]["total_customers"] += 1
        stats[assigned]["by_status"][status] = stats[assigned]["by_status"].get(status, 0) + 1

    result = "📊 销售业绩统计\n" + "=" * 50 + "\n\n"

    for sales_id, data in stats.items():
        if data["total_customers"] == 0:
            continue

        result += f"👤 {data['name']} ({sales_id})\n"
        result += f"   总客户数：{data['total_customers']}\n"
        result += f"   状态分布：\n"
        for status, count in data["by_status"].items():
            result += f"     - {status}: {count}\n"
        result += "\n"

    return result


def monitor_system_tool() -> str:
    """系统监控"""
    report_lines = ["📊 CRM 系统监控报告", "=" * 50, ""]

    total_customers = len(customers)
    total_processes = len(process_instances)
    pending = len(get_pending_reviews())

    report_lines.append(f"📈 系统统计:")
    report_lines.append(f"   - 总客户数: {total_customers}")
    report_lines.append(f"   - 总流程数: {total_processes}")
    report_lines.append(f"   - 待审核: {pending}")
    report_lines.append("")

    timeout_reviews = check_review_timeout()
    if timeout_reviews:
        report_lines.append(f"⚠️ 发现 {len(timeout_reviews)} 个审核超时:")
        for item in timeout_reviews:
            report_lines.append(
                f"   - {item['review_id']} - {item['operation']} - 已等待 {item['duration_minutes']} 分钟")
        report_lines.append("")

    if not timeout_reviews and pending == 0:
        report_lines.append("✅ 系统运行正常，无异常情况")

    report_lines.append("")
    report_lines.append("=" * 50)
    report_lines.append(f"🕐 监控时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(report_lines)


def analyze_review_tool(review_id: str) -> str:
    """分析审核任务"""
    review_task = None
    for review in pending_reviews:
        if review["id"] == review_id:
            review_task = review
            break

    if not review_task:
        return f"❌ 审核任务不存在：{review_id}"

    risk_analysis = assess_review_risk(review_id)

    report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 审核分析报告

审核ID：{review_id}
审核项：{review_task['operation']}

风险评估：{risk_analysis['risk_emoji']} {risk_analysis['risk_label']}
风险评分：{risk_analysis['risk_score']}/100

AI 建议：{risk_analysis['recommendation_text']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    return report


def smart_approve_tool(review_id: str) -> str:
    """智能批准审核"""
    risk_analysis = assess_review_risk(review_id)

    if "error" in risk_analysis:
        return risk_analysis["error"]

    task = approve_review(review_id)
    if not task:
        return f"❌ 审核任务不存在：{review_id}"

    record_review_decision(review_id, "approved")

    # 恢复流程
    for proc in process_instances.values():
        if proc["status"] == "paused":
            proc["current_step"] += 1
            proc["status"] = "running"
            update_process(proc["id"], proc)

            # 继续执行剩余步骤
            while proc["current_step"] < len(proc["tasks"]):
                task_obj = proc["tasks"][proc["current_step"]]
                task_name = task_obj["name"]

                if task_obj["need_review"]:
                    # 又遇到需要审核的
                    return f"✅ 审核已批准，流程继续执行中，但又遇到需要审核的步骤"

                result = execute_customer_task(task_name, proc["customer_data"], proc)
                proc["results"].append(result)
                proc["current_step"] += 1
                update_process(proc["id"], proc)

            proc["status"] = "completed"
            update_process(proc["id"], proc)
            return "✅ 审核已批准，流程已全部完成！"

    return "✅ 审核已批准"


# ========== 8. LLM 和 Agent 配置 ==========

llm = ChatOpenAI(
    api_key="sk-eyy7q4sejyOBK9FgbxjfHVmcPiw3ttLXR05FTMMilK9gFGFB",
    base_url="https://api.moonshot.cn/v1",
    model="moonshot-v1-8k",
    temperature=0
)

tools = [
    StructuredTool.from_function(
        func=add_customer_tool,
        name="add_customer",
        description="添加新客户。必需：name, contact_person, phone, industry, source"
    ),
    StructuredTool.from_function(
        func=query_customer_tool,
        name="query_customer",
        description="查询客户信息"
    ),
    StructuredTool.from_function(
        func=check_followup_tool,
        name="check_followup",
        description="检查需要跟进的客户"
    ),
    StructuredTool.from_function(
        func=sales_performance_tool,
        name="sales_performance",
        description="查看销售业绩统计"
    ),
    StructuredTool.from_function(
        func=monitor_system_tool,
        name="monitor_system",
        description="监控系统状态"
    ),
    StructuredTool.from_function(
        func=analyze_review_tool,
        name="analyze_review",
        description="分析审核任务风险"
    ),
    StructuredTool.from_function(
        func=smart_approve_tool,
        name="smart_approve",
        description="智能批准审核"
    )
]

AGENT_PROMPT = """你是智能 CRM 系统助理，负责客户关系管理。

核心能力：
1. 客户录入和管理
2. 销售分配和推荐
3. 跟进提醒
4. 业绩统计
5. 智能审核

工作流程：
- 用户说"添加客户" → 调用 add_customer，询问必需信息
- 用户说"查询客户" → 调用 query_customer
- 用户说"今天要跟进谁" → 调用 check_followup
- 用户说"销售业绩" → 调用 sales_performance
- 用户说"分析审核" → 调用 analyze_review
- 用户说"批准" → 调用 smart_approve

重要规则：
- 客户信息要完整
- 用专业、高效的语气
- AI 会自动推荐最合适的销售负责人
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", AGENT_PROMPT),
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

# ========== 9. FastAPI 应用 ==========

app = FastAPI()


def success(data=None, msg="ok"):
    return {"code": 0, "msg": msg, "data": data}


def error(msg="error", code=1):
    return {"code": code, "msg": msg, "data": None}


@app.get("/")
def root():
    return {
        "message": "智能 CRM 系统",
        "version": "1.0",
        "features": ["客户管理", "AI推荐销售", "跟进提醒", "智能审核"]
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


@app.get("/api/customers")
def list_customers():
    """列出所有客户"""
    return success(customers)


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str):
    """获取客户详情"""
    if customer_id in customers:
        return success(customers[customer_id])
    return error("客户不存在")


@app.get("/api/sales-team")
def list_sales():
    """查看销售团队"""
    return success(sales_team)


@app.get("/api/processes")
def list_processes():
    """查看所有流程"""
    processes = []
    for proc_id, proc in process_instances.items():
        viz = visualize_process(proc)
        processes.append(viz)
    return success(processes)


@app.get("/api/reviews")
def list_reviews():
    """查看待审核任务"""
    return success(get_pending_reviews())


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("🚀 智能 CRM 系统")
    print("=" * 60)
    print("✨ 功能：")
    print("  - ✅ 客户管理")
    print("  - ✅ AI 智能推荐销售负责人")
    print("  - ✅ 跟进提醒")
    print("  - ✅ 业绩统计")
    print("  - ✅ 智能审核")
    print("=" * 60)
    print("📖 API 文档：http://localhost:8000/docs")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)