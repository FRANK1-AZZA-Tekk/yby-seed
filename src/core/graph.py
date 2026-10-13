"""Grafo mínimo de conversa do YBY SEED."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.core.llm import LLMClient
from src.core.memory import MemoryStore
from src.core.rag import build_index, search


class AskState(TypedDict):
    question: str
    route: str
    answer: str
    citations: list[str]


def build_ask_graph(
    llm: LLMClient | None = None,
    cite: bool = False,
    remember: bool = False,
    memory: MemoryStore | None = None,
):
    """Constrói o fluxo mínimo: route -> respond."""
    client = llm or LLMClient()
    store = memory or MemoryStore()
    index = build_index() if cite else []

    def route(state: AskState) -> AskState:
        question = state["question"].strip()
        if not question:
            raise ValueError("A pergunta não pode ser vazia.")
        return {**state, "route": "direct_answer", "citations": []}

    def respond(state: AskState) -> AskState:
        question = state["question"]
        context_parts: list[str] = []
        citations: list[str] = []

        if cite:
            results = search(question, index)
            if results:
                context_parts.append("Documentos:\n" + "\n\n".join(chunk.text for chunk in results))
                citations.extend(f"{chunk.source}:{chunk.line}" for chunk in results)

        memories = store.search(question)
        if memories:
            context_parts.append(
                "Memórias relevantes:\n"
                + "\n".join(f"Q: {m.question}\nA: {m.answer}" for m in memories)
            )
            citations.extend(f"memory:{number}" for number, _ in enumerate(memories, start=1))

        if context_parts:
            prompt = f"Responda usando apenas o contexto abaixo.\n\n{chr(10).join(context_parts)}\n\nPergunta: {question}"
        else:
            prompt = question

        answer = client.generate(prompt)

        if remember:
            store.add(question, answer)

        return {**state, "answer": answer, "citations": citations}

    graph = StateGraph(AskState)
    graph.add_node("route", route)
    graph.add_node("respond", respond)
    graph.set_entry_point("route")
    graph.add_edge("route", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


def ask(
    question: str,
    llm: LLMClient | None = None,
    cite: bool = False,
    remember: bool = False,
    memory: MemoryStore | None = None,
) -> tuple[str, list[str]]:
    graph = build_ask_graph(llm, cite=cite, remember=remember, memory=memory)
    result = graph.invoke({"question": question, "route": "", "answer": "", "citations": []})
    return result["answer"], result["citations"]
