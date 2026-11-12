"""Servidor MCP (stdio + HTTP/SSE montado no FastAPI)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from mcp.server.mcpserver import MCPServer

from src.yby_seed.mcp import tools

_MCP: MCPServer | None = None


def build_mcp_server() -> MCPServer:
    server = MCPServer(
        "yby-seed",
        instructions=(
            "Ferramentas determinísticas YBY SEED: RAG pgvector, inspeção de repo local, "
            "headroom GPU, MQTT e simulação Vast (dry-run)."
        ),
    )

    @server.tool(name="search_knowledge_base")
    async def search_knowledge_base(query: str, domain: str | None = None) -> dict[str, Any]:
        """Consulta a base técnica pgvector."""
        return await tools.search_knowledge_base(query, domain)

    @server.tool(name="inspect_local_repo")
    def inspect_local_repo(repo_path: str, file_pattern: str = "**/*") -> dict[str, Any]:
        """Inspeciona arquivos de projetos locais autorizados."""
        return tools.inspect_local_repo(repo_path, file_pattern)

    @server.tool(name="check_gpu_headroom")
    def check_gpu_headroom() -> dict[str, Any]:
        """Verifica VRAM livre (GTX 1650, 4GB)."""
        return tools.check_gpu_headroom()

    @server.tool(name="publish_mqtt_command")
    def publish_mqtt_command(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Publica comando no Mosquitto em `yby/seed/cmd/...`."""
        return tools.publish_mqtt_command(topic, payload)

    @server.tool(name="simulate_vast_forge")
    def simulate_vast_forge(task: str) -> dict[str, Any]:
        """Simula missão Vast.ai sem gastar saldo (dry-run)."""
        return tools.simulate_vast_forge(task)

    @server.tool(name="get_repo_map")
    def get_repo_map(repo_path: str, domain: str | None = None) -> dict[str, Any]:
        """Mapa compacto de símbolos Python/C++ e manifesto GPIO."""
        return tools.get_repo_map(repo_path, domain=domain)

    return server


def get_mcp_server() -> MCPServer:
    global _MCP
    if _MCP is None:
        _MCP = build_mcp_server()
    return _MCP


def mount_mcp_on_fastapi(app: FastAPI) -> None:
    """Monta transporte Streamable HTTP em `/mcp` e SSE legado em `/mcp/sse`."""
    mcp = get_mcp_server()
    stream_app = mcp.streamable_http_app(streamable_http_path="/", host="127.0.0.1")
    sse_app = mcp.sse_app(sse_path="/sse", message_path="/messages/", host="127.0.0.1")
    app.mount("/mcp", stream_app)
    app.mount("/mcp/sse", sse_app)


def run_stdio_server() -> None:
    """Entrada stdio para Cursor IDE / agentes CLI."""
    get_mcp_server().run("stdio")


def main() -> None:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        run_stdio_server()
    else:
        print("Uso: python -m src.yby_seed.mcp.server stdio", flush=True)


if __name__ == "__main__":
    main()
