"""Grafo mínimo de conversa do YBY SEED."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.core.llm import LLMClient


class AskState(TypedDict):
    question: str
    route: str
    answer: str


def build_ask_graph(llm: LLMClient | None = None):
    """Constrói o fluxo mínimo: route -> respond."""
    client = llm or LLMClient()

    def route(state: AskState) -> AskState:
        question = state["question"].strip()
        if not question:
            raise ValueError("A pergunta não pode ser vazia.")
        return {**state, "route": "direct_answer"}

    def respond(state: AskState) -> AskState:
        answer = client.generate(state["question"])
        return {**state, "answer": answer}

    graph = StateGraph(AskState)
    graph.add_node("route", route)
    graph.add_node("respond", respond)
    graph.set_entry_point("route")
    graph.add_edge("route", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


def ask(question: str, llm: LLMClient | None = None) -> str:
    graph = build_ask_graph(llm)
    result = graph.invoke({"question": question, "route": "", "answer": ""})
    return result["answer"]
