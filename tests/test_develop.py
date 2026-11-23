"""Testes do develop multi-camada (planner scripted; sem Cursor/OpenRouter reais)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from src.develop.cursor_send import preview_send, send_layer
from src.develop.export_md import export_layer
from src.develop.gate import can_send
from src.develop.planner import ScriptedDevelopPlanner
from src.develop.schemas import DevelopPlan, Layer
from src.develop.store import load_plan, save_plan, set_layer_status
from src.develop.validate import PlanValidationError, validate_plan
from src.main import cli


def _two_layer_plan(**kwargs) -> DevelopPlan:
    return DevelopPlan(
        id=kwargs.get("id", "demo"),
        pedido="demo duas camadas",
        base_commit=kwargs.get("base_commit", "HEAD"),
        layers=[
            Layer(
                id="L1",
                depends_on=[],
                objetivo="primeira",
                allowed_files=["src/develop/schemas.py"],
                non_goals=["não tocar ask"],
                acceptance=["L1 ok"],
                verification=["pytest -q"],
                status="preparada",
            ),
            Layer(
                id="L2",
                depends_on=["L1"],
                objetivo="segunda",
                allowed_files=["src/develop/cli.py"],
                non_goals=[],
                acceptance=["L2 ok"],
                verification=[],
                status="preparada",
            ),
        ],
    )


def test_validate_ok_and_rejects(tmp_path: Path) -> None:
    plan = _two_layer_plan()
    # repo_root = yby-seed checkout
    root = Path.cwd()
    validate_plan(plan, repo_root=root)

    bad = _two_layer_plan()
    bad.layers[0].allowed_files = ["../outside.py"]
    try:
        validate_plan(bad, repo_root=root)
        assert False, "deveria rejeitar .."
    except PlanValidationError:
        pass

    cycle = DevelopPlan(
        id="c",
        layers=[
            Layer(id="A", depends_on=["B"], objetivo="a", allowed_files=["src/main.py"]),
            Layer(id="B", depends_on=["A"], objetivo="b", allowed_files=["src/main.py"]),
        ],
    )
    try:
        validate_plan(cycle, repo_root=root)
        assert False, "deveria rejeitar ciclo"
    except PlanValidationError:
        pass

    missing = _two_layer_plan()
    missing.layers[1].depends_on = ["L9"]
    try:
        validate_plan(missing, repo_root=root)
        assert False, "deveria rejeitar dep"
    except PlanValidationError:
        pass


def test_scripted_plan_save_load(tmp_path: Path) -> None:
    root = tmp_path / "develop"
    planner = ScriptedDevelopPlanner([_two_layer_plan()])
    plan = planner.plan("pedido", repo_root=Path.cwd(), base_commit="abc")
    path = save_plan(plan, root=root)
    assert path.is_file()
    loaded = load_plan(plan.id, root=root)
    assert loaded.base_commit == "abc"
    assert len(loaded.layers) == 2


def test_l2_bloqueada_ate_accept_l1(tmp_path: Path) -> None:
    root = tmp_path / "develop"
    plan = _two_layer_plan()
    save_plan(plan, root=root)
    ok, reason = can_send(plan, "L2")
    assert ok is False
    assert "L1" in reason

    set_layer_status(plan, "L1", "enviada", root=root)
    ok, _ = can_send(plan, "L2")
    assert ok is False

    set_layer_status(plan, "L1", "aceita", root=root)
    ok, reason = can_send(plan, "L2")
    assert ok is True


def test_reject_l1_mantem_bloqueio_l2(tmp_path: Path) -> None:
    plan = _two_layer_plan()
    set_layer_status(plan, "L1", "rejeitada", root=tmp_path / "d")
    ok, _ = can_send(plan, "L2")
    assert ok is False


def test_send_dry_run_e_fake_cursor(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "develop"
    plan = _two_layer_plan(base_commit="HEAD")
    save_plan(plan, root=root)
    set_layer_status(plan, "L1", "aceita", root=root)  # liberar L2 depois
    # send L1 first path: L1 has no deps
    plan2 = load_plan(plan.id, root=root)
    plan2.layer("L1").status = "preparada"  # type: ignore[union-attr]
    save_plan(plan2, root=root)

    fake = tmp_path / "fake-cursor"
    fake.write_text("#!/bin/sh\necho \"$@\" > \"$0.argv\"\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("YBY_CURSOR_BIN", str(fake))

    preview = preview_send(plan2, "L1", repo_root=Path.cwd())
    assert preview.blocked is None
    assert preview.binary == str(fake)

    ok, msg = send_layer(
        plan2,
        "L1",
        repo_root=Path.cwd(),
        root=root,
        dry_run=True,
        confirm=False,
    )
    assert ok is True
    assert "dry-run" in msg
    assert load_plan(plan.id, root=root).layer("L1").status == "preparada"  # type: ignore[union-attr]

    # skip real worktree if git fails in sandbox — mock ensure
    monkeypatch.setattr("src.develop.cursor_send.ensure_worktree", lambda **_k: None)

    class Done:
        returncode = 0

    ok, msg = send_layer(
        plan2,
        "L1",
        repo_root=Path.cwd(),
        root=root,
        dry_run=False,
        confirm=False,
        run_fn=lambda argv, cwd: Done(),
    )
    assert ok is True
    assert "enviada" in msg
    reloaded = load_plan(plan.id, root=root)
    assert reloaded.layer("L1").status == "enviada"  # type: ignore[union-attr]
    assert reloaded.layer("L1").status != "aceita"  # type: ignore[union-attr]
    # L2 still blocked
    assert can_send(reloaded, "L2")[0] is False


def test_export_md(tmp_path: Path) -> None:
    root = tmp_path / "develop"
    plan = _two_layer_plan()
    save_plan(plan, root=root)
    path = export_layer(plan, "L1", root=root)
    text = path.read_text(encoding="utf-8")
    assert "L1" in text
    assert "não tocar ask" in text


def test_send_bin_missing_nao_marca_enviada(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "develop"
    plan = _two_layer_plan()
    save_plan(plan, root=root)
    monkeypatch.delenv("YBY_CURSOR_BIN", raising=False)
    monkeypatch.setattr("src.develop.cursor_send.detect_cursor_bin", lambda **_k: None)
    ok, msg = send_layer(
        plan,
        "L1",
        repo_root=Path.cwd(),
        root=root,
        dry_run=False,
        confirm=False,
    )
    assert ok is False
    assert "ausente" in msg.casefold()
    assert load_plan(plan.id, root=root).layer("L1").status == "preparada"  # type: ignore[union-attr]


def test_ask_smoke() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["ask", "--help"])
    assert result.exit_code == 0
