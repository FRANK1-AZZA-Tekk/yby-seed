from typing import Literal

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from integrations.yby_core.app.router import get_model
from integrations.yby_core.app.state import YBYState
from integrations.yby_core.app.tools.files import read_yby_file, write_yby_file
from integrations.yby_core.app.tools.mqtt import publish_mqtt
from integrations.yby_core.app.tools.platformio import platformio_build
from integrations.yby_core.app.tools.qdrant import search_yby_memory


tools = [
    read_yby_file,
    write_yby_file,
    platformio_build,
    publish_mqtt,
    search_yby_memory,
]

tool_node = ToolNode(tools)

SYSTEM_PROMPT = """
Você é o YBY Core, orquestrador técnico do ecossistema YBY.

Regras:
1. Responda sempre em português do Brasil.
2. Use ferramentas apenas quando necessário.
3. Não execute ações destrutivas sem aprovação explícita.
4. Para firmware, use PlatformIO e valide o projeto antes do build.
5. Para dados sensíveis, prefira o modelo local.
6. Se faltar informação essencial, pergunte ao usuário.
7. Nunca invente pinos, bibliotecas, comandos ou caminhos.
"""


def classify_task(state: YBYState) -> dict:
    last_message = state["messages"][-1].content.lower()

    if any(word in last_message for word in ["esp32", "firmware", "platformio"]):
        task_type = "firmware"
    elif any(word in last_message for word in ["pesquise", "compare", "preço"]):
        task_type = "research"
    elif any(word in last_message for word in ["memória", "documento", "manual"]):
        task_type = "memory"
    else:
        task_type = "chat"

    return {"task_type": task_type}


def call_model(state: YBYState) -> dict:
    model = get_model(state["task_type"])

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]

    response = model.bind_tools(tools).invoke(messages)

    return {"messages": [response]}


def should_continue(state: YBYState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]

    if getattr(last_message, "tool_calls", None):
        return "tools"

    return "__end__"


def finalize(state: YBYState) -> dict:
    last_message = state["messages"][-1]
    return {"result": last_message.content}


builder = StateGraph(YBYState)

builder.add_node("classify", classify_task)
builder.add_node("agent", call_model)
builder.add_node("tools", tool_node)
builder.add_node("finalize", finalize)

builder.add_edge(START, "classify")
builder.add_edge("classify", "agent")

builder.add_conditional_edges(
    "agent",
    should_continue,
    ["tools", "__end__"],
)

builder.add_edge("tools", "agent")
builder.add_edge("agent", "finalize")
builder.add_edge("finalize", END)

yby_graph = builder.compile()
