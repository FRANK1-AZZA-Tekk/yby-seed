import pytest

from src.yby_seed.mcp import tools
from src.yby_seed.mcp.server import build_mcp_server


def test_inspect_local_repo_blocks_traversal(tmp_path, monkeypatch) -> None:
    allowed = tmp_path / "workspace"
    allowed.mkdir()
    (allowed / "ok.py").write_text("x", encoding="utf-8")
    monkeypatch.setenv("YBY_MCP_REPO_ROOTS", str(allowed))

    payload = tools.inspect_local_repo(str(allowed), "*.py")
    assert payload["file_count"] == 1

    with pytest.raises(PermissionError):
        tools.inspect_local_repo("/etc", "*")


def test_publish_mqtt_command_topic_guard() -> None:
    with pytest.raises(PermissionError):
        tools.publish_mqtt_command("hack/topic", {"x": 1})


def test_check_gpu_headroom_shape() -> None:
    payload = tools.check_gpu_headroom()
    assert "decision" in payload
    assert "vram_free_mb" in payload


def test_simulate_vast_forge_dry_run() -> None:
    payload = tools.simulate_vast_forge("quantize")
    assert payload["dry_run"] is True
    assert payload["mission"] == "quantize"


def test_build_mcp_server_lists_tools() -> None:
    server = build_mcp_server()
    tool_names = {tool.name for tool in server._tool_manager.list_tools()}  # noqa: SLF001
    assert "search_knowledge_base" in tool_names
    assert "simulate_vast_forge" in tool_names
