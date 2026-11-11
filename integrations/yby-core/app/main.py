import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from integrations.yby_core.app.graph import yby_graph


app = FastAPI(title="YBY Core", version="0.3.1")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


class ChatRequest(BaseModel):
    message: str
    project_path: str = "projects/yby-seed"


class ChatResponse(BaseModel):
    answer: str
    task_type: str
    needs_approval: bool


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "yby-core"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    initial_state = {
        "messages": [
            {
                "role": "user",
                "content": request.message,
            }
        ],
        "task_type": "chat",
        "project_path": request.project_path,
        "needs_approval": False,
        "result": "",
    }

    final_state = await yby_graph.ainvoke(initial_state)

    return ChatResponse(
        answer=final_state["result"],
        task_type=final_state["task_type"],
        needs_approval=final_state["needs_approval"],
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    initial_state = {
        "messages": [
            {
                "role": "user",
                "content": request.message,
            }
        ],
        "task_type": "chat",
        "project_path": request.project_path,
        "needs_approval": False,
        "result": "",
    }

    config = {
        "configurable": {
            "thread_id": "yby-local",
        }
    }

    async def event_generator():
        yield sse_event(
            "start",
            {
                "message": request.message,
                "project_path": request.project_path,
            },
        )

        final_answer = ""

        try:
            async for event in yby_graph.astream_events(
                initial_state,
                version="v2",
                config=config,
            ):
                event_type = event.get("event")

                if event_type == "on_tool_start":
                    yield sse_event(
                        "tool_start",
                        {
                            "tool": event["name"],
                            "run_id": event["run_id"],
                            "input": event["data"].get("input", {}),
                        },
                    )

                elif event_type == "on_tool_end":
                    output = event["data"].get("output", "")

                    if hasattr(output, "content"):
                        output = output.content

                    yield sse_event(
                        "tool_end",
                        {
                            "tool": event["name"],
                            "run_id": event["run_id"],
                            "output": str(output)[:4000],
                        },
                    )

                elif event_type == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = getattr(chunk, "content", "")

                    if isinstance(content, list):
                        content = "".join(
                            part.get("text", "")
                            for part in content
                            if isinstance(part, dict)
                        )

                    if not content:
                        continue

                    final_answer += content

                    yield sse_event(
                        "token",
                        {
                            "node": event.get("metadata", {}).get(
                                "langgraph_node",
                                "unknown",
                            ),
                            "content": content,
                        },
                    )

            yield sse_event(
                "done",
                {
                    "answer": final_answer,
                },
            )

        except Exception as error:
            yield sse_event(
                "error",
                {
                    "message": str(error),
                },
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
