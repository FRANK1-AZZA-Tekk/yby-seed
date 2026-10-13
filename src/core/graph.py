"""Grafo mínimo de conversa do YBY SEED."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.core.llm import LLMClient
from src.core.rag import build_index, search


class AskState(TypedDict):
    question: str
    route: str
    answer: str
    citations: list[str]


def build_ask_graph(llm: LLMClient | None = None, cite: bool = False):
    """Constrói o fluxo mínimo: route -> respond."""
    client = llm or LLMClient()
    index = build_index() if cite else []

    def route(state: AskState) -> AskState:
        question = state["question"].strip()
        if not question:
            raise ValueError("A pergunta não pode ser vazia.")
        return {**state, "route": "direct_answer", "citations": []}

    def respond(state: AskState) -> AskState:
        question = state["question"]
        if cite:
            results = search(question, index)
            context = "\n\n".join(chunk.text for chunk in results)
            prompt = f"Responda usando apenas o contexto abaixo.\n\nContexto:\n{context}\n\nPergunta: {question}"
            answer = client.generate(prompt)
            citations = [f"{chunk.source}:{chunk.line}" for chunk in results]
        else:
            answer = client.generate(question)
            citations = []
        return {**state, "answer": answer, "citations": citations}

    graph = StateGraph(AskState)
    graph.add_node("route", route)
    graph.add_node("respond", respond)
    graph.set_entry_point("route")
    graph.add_edge("route", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


def ask(question: str, llm: LLMClient | None = None, cite: bool = False) -> tuple[str, list[str]]:
    graph = build_ask_graph(llm, cite=cite)
    result = graph.invoke({"question": question, "route": "", "answer": "", "citations": []})
    return result["answer"], result["citations"]
