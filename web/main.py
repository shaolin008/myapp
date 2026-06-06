from fastapi import FastAPI
import json
from pydantic import BaseModel
from langchain_core.tools import StructuredTool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# --- 1. 全局数据和辅助函数 (必须在最前面) ---
pending_action = None

persons = {}
next_id = 1

def save_data():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "next_id": next_id,
                "persons": persons
            },
            f,
            ensure_ascii=False
        )

def load_data():
    global next_id, persons
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            next_id = data["next_id"]
            persons = {int(k): v for k, v in data["persons"].items()}
    except FileNotFoundError:
        pass

# 初始化加载数据
load_data()

# --- 2. LLM 和 Agent 工具定义 ---

# 初始化 LLM (Kimi)
llm = ChatOpenAI(
    api_key="sk-eyy7q4sejyOBK9FgbxjfHVmcPiw3ttLXR05FTMMilK9gFGFB",
    base_url="https://api.moonshot.cn/v1",
    model="moonshot-v1-8k",
    temperature=0
)

# 定义 Tool 函数
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
    return f"成功添加人员：{name}，年龄 {age}，部门 {department}"
def guarded_add_person(name: str, age: int, department: str) -> str:
    global pending_action

    # 没有确认，永远不允许执行
    if pending_action != ("add_person", name, age, department):
        pending_action = ("add_person", name, age, department)
        return (
            "⚠️ 该操作属于高风险写操作，需要人工确认。\n"
            f"请回复：确认添加人员：{name}，{age}，{department}"
        )

    # 已确认，真正执行
    pending_action = None
    return add_person_tool_func(name, age, department)

# 包装为 Tool
add_person_tool = StructuredTool.from_function(
    func=guarded_add_person,
    name="add_person",
    description="添加人员（L2 高风险操作，需人工确认）"
)

# 代理配置
tools = [add_person_tool]
base_prompt = hub.pull("hwchase17/openai-tools-agent")
SAFETY_SYSTEM_PROMPT = """

你是一个企业内部 AI 助理，必须严格遵守以下规则：

1. 添加人员属于 L2 高风险写操作。
2. 在以下“确认格式”出现之前，禁止调用 add_person 工具。
3. 唯一有效的确认格式是：
   “确认添加人员：姓名，年龄，部门”
4. 任何其他说法（如“我同意”“已授权”“可以执行”）一律视为未确认。
5. 未确认时，你只能提示用户使用正确的确认格式，禁止调用工具。
6. 一旦检测到正确的确认格式，必须立即调用 add_person 工具。
"""


prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SAFETY_SYSTEM_PROMPT),
        *base_prompt.messages
    ]
)

# 创建 Agent 和 AgentExecutor
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# --- 3. 执行 Agent 任务 (测试用) ---
# print(">>> 开始执行 Agent 任务...")
# try:
#     agent_executor.invoke({"input": "Add a new person with name: John, age: 28, and department: HR."})
# except Exception as e:
#     print(f"Agent execution failed: {e}")

# --- 4. FastAPI 应用定义 ---

app = FastAPI()

# 业务逻辑函数 (API 使用)
def add_person(name, age, dep):
    global next_id
    person_id = next_id
    next_id += 1
    persons[person_id] = {
        "id": person_id,
        "name": name,
        "age": age,
        "dep": dep
    }
    save_data()
    return person_id

def seek_person(person_id: int):
    return persons.get(person_id)

def list_persons():
    return persons

def success(data=None, msg="ok"):
    return {
        "code": 0,
        "msg": msg,
        "data": data
    }

def error(msg="error", code=1):
    return {
        "code": code,
        "msg": msg,
        "data": None
    }

class PersonCreate(BaseModel):
    name: str
    age: int
    dep: str

@app.post("/person")
def api_add_person(person: PersonCreate):
    # 注意：这里并没有去重检查逻辑，原代码的 success_flag 逻辑有点问题，这里简化处理
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
    return success(list_persons())
if __name__ == "__main__":
    print(">>> Agent 已启动，等待用户输入...")

    while True:
        user_input = input("用户：")
        result = agent_executor.invoke({
            "input": user_input
        })
        print("AI：", result["output"])

