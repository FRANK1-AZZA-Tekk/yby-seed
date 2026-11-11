from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class YBYState(TypedDict):
    messages: Annotated[list, add_messages]
    task_type: Literal["chat", "firmware", "research", "memory", "hardware"]
    project_path: str
    needs_approval: bool
    result: str
