import pytest

from src.yby_seed.mcp import tools
from src.yby_seed.mcp.server import build_mcp_server


def test_path_traversal_blocked(tmp_path, monkeypatch) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("YBY_MCP_REPO_ROOTS", str(root))
    with pytest.raises(PermissionError):
        tools.inspect_local_repo("/etc/passwd", "*")


def test_destructive_mqtt_payload_blocked() -> None:
    with pytest.raises(PermissionError):
        tools.publish_mqtt_command("yby/seed/cmd/reboot", {"shutdown": True})


def test_mcp_tool_schemas_present() -> None:
    server = build_mcp_server()
    tool_names = {tool.name for tool in server._tool_manager.list_tools()}  # noqa: SLF001
    expected = {
        "search_knowledge_base",
        "inspect_local_repo",
        "check_gpu_headroom",
        "publish_mqtt_command",
        "simulate_vast_forge",
        "get_repo_map",
    }
    assert expected.issubset(tool_names)


def test_gpu_headroom_structure() -> None:
    payload = tools.check_gpu_headroom()
    assert payload["vram_cap_mb"] == 4096
