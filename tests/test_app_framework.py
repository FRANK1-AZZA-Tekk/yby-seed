"""Testes do framework (Camada A + pipeline + Camada C esqueleto; sem LLM)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from src.app import (
    App,
    CommandPipeline,
    Layer,
    LayerStatus,
    create_app,
    default_pipeline,
    load_settings,
)
from src.app.skills_layer import (
    AutoRunRefused,
    SkillsLayer,
    refuse_auto_run,
    request_human_confirm,
)


def test_load_settings_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("YBY_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("YBY_SKILLS_MODE", raising=False)
    monkeypatch.delenv("YBY_MEMORY_BACKEND", raising=False)
    settings = load_settings(tmp_path)
    assert settings.project_root == tmp_path
    assert settings.data_dir == tmp_path / ".yby"
    assert settings.llm_provider_preference == "auto"
    assert settings.skills_mode == "dry_run"
    assert settings.memory_backend == "none"
    assert settings.has_openrouter_key is False
    assert settings.ux_locale == "pt"


def test_layer_registry_form_briefing_ready_skills_partial() -> None:
    app = create_app()
    assert app.layers.get(Layer.FORM).status == LayerStatus.READY
    assert app.layers.get(Layer.BRIEFING).status == LayerStatus.READY
    assert app.layers.get(Layer.SKILLS).status == LayerStatus.PARTIAL
    assert app.layers.get(Layer.MEMORY).status == LayerStatus.PLANNED
    table = app.layers.format_table()
    assert "Forma do produto" in table
    assert "Briefing" in table
    assert "partial" in table


def test_default_pipeline_registers_skills_plugin() -> None:
    pipe = default_pipeline()
    plugins = pipe.plugins()
    assert len(plugins) == 1
    assert plugins[0].layer == Layer.SKILLS
    assert isinstance(plugins[0], SkillsLayer)


def test_register_command_plugin_protocol() -> None:
    out = io.StringIO()
    app = App(settings=load_settings(), stdout=out, stderr=io.StringIO())

    def _ping(_app: App, _args: list[str]) -> int:
        _app.stdout.write("pong\n")
        return 0

    app.register_command("ping", _ping)
    assert app.dispatch(["ping"]) == 0
    assert "pong" in out.getvalue()


def test_dispatch_help_and_status() -> None:
    out = io.StringIO()
    err = io.StringIO()
    app = App(settings=load_settings(), stdout=out, stderr=err)
    assert app.dispatch(["help"]) == 0
    help_text = out.getvalue()
    assert "/brief" in help_text
    assert "/skills" in help_text
    out.seek(0)
    out.truncate(0)
    assert app.dispatch(["status"]) == 0
    status = out.getvalue()
    assert "Skills mode: dry_run" in status
    assert "Camadas partial: C" in status
    assert app.dispatch(["layers"]) == 0


def test_dispatch_unknown_command() -> None:
    err = io.StringIO()
    app = App(settings=load_settings(), stdout=io.StringIO(), stderr=err)
    assert app.dispatch(["nope"]) == 2
    assert "desconhecido" in err.getvalue()


def test_handle_line_quit_and_slash() -> None:
    out = io.StringIO()
    app = App(settings=load_settings(), stdout=out, stderr=io.StringIO())
    assert app.handle_line("quit") == 0
    assert app.handle_line("/status") is None
    assert "YBY SEED" in out.getvalue()


def test_handle_line_chat_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    out = io.StringIO()
    app = App(settings=load_settings(), stdout=out, stderr=io.StringIO())

    monkeypatch.setattr(
        "modules.llm_brain.load_llm_config",
        lambda: type("C", (), {"provider": "mock", "model": "m"})(),
    )
    monkeypatch.setattr(
        "modules.llm_brain.ask_llm", lambda text, config=None: f"eco:{text}"
    )

    assert app.handle_line("olá hub") is None
    assert "eco:olá hub" in out.getvalue()


def test_yby_seed_facade_importable() -> None:
    from yby_seed import main

    assert callable(main)


def test_skills_discover_and_list(tmp_path: Path) -> None:
    """Discovery lê SKILL.md real do repo (sem Ollama)."""
    out = io.StringIO()
    err = io.StringIO()
    # project_root = repo root so skills/ exists
    root = Path(__file__).resolve().parents[1]
    settings = load_settings(root)
    app = App(settings=settings, stdout=out, stderr=err)

    assert app.dispatch(["skills"]) == 0
    text = out.getvalue()
    assert "backup-automation" in text
    assert "file-operations" in text
    assert "DRY-RUN" not in text or "dry-run" in text.lower() or "Dry-run" in text
    assert "não disponível" in text or "confirmação humana" in text


def test_skill_dry_run_preview() -> None:
    out = io.StringIO()
    err = io.StringIO()
    root = Path(__file__).resolve().parents[1]
    app = App(settings=load_settings(root), stdout=out, stderr=err)

    assert app.dispatch(["skill", "backup-automation", "backup dos PDFs"]) == 0
    text = out.getvalue()
    assert "DRY-RUN" in text
    assert "backup-automation" in text
    assert "nenhum código seria executado" in text


def test_skill_unknown_returns_error() -> None:
    err = io.StringIO()
    root = Path(__file__).resolve().parents[1]
    app = App(settings=load_settings(root), stdout=io.StringIO(), stderr=err)
    assert app.dispatch(["skill", "nao-existe"]) == 2
    assert "não encontrada" in err.getvalue()


def test_skill_run_refused() -> None:
    err = io.StringIO()
    root = Path(__file__).resolve().parents[1]
    app = App(settings=load_settings(root), stdout=io.StringIO(), stderr=err)
    assert app.dispatch(["skill", "run", "backup-automation"]) == 2
    assert "recusada" in err.getvalue().lower() or "ERRO" in err.getvalue()


def test_refuse_auto_run_and_confirm_stub() -> None:
    with pytest.raises(AutoRunRefused):
        refuse_auto_run("backup-automation")
    assert request_human_confirm(auto=True, skill_name="x") is False
    assert request_human_confirm(auto=False, skill_name="x") is False


def test_skills_layer_discover_empty_dir(tmp_path: Path) -> None:
    layer = SkillsLayer()
    empty = tmp_path / "skills"
    empty.mkdir()
    assert layer.discover(empty) == []


def test_skills_thin_reader_fallback_on_bad_yaml(tmp_path: Path) -> None:
    """YAML inválido: SkillManager falha; thin reader ainda lista a skill."""
    skill_dir = tmp_path / "skills" / "broken-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: broken-skill\n"
        "description: Texto com dois pontos: quebra YAML\n"
        "compatibility: python\nlicense: MIT\n---\n\nBody.\n",
        encoding="utf-8",
    )
    layer = SkillsLayer()
    found = layer.discover(tmp_path / "skills")
    assert len(found) == 1
    assert found[0].name == "broken-skill"


def test_skills_layer_preview_steps(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Skill de teste\n"
        "compatibility: python\nlicense: MIT\n---\n\n## Quando Usar\n\nDemo.\n",
        encoding="utf-8",
    )
    layer = SkillsLayer()
    preview = layer.preview(tmp_path / "skills", "demo-skill", request="olá")
    assert preview.would_execute is False
    assert preview.skill.name == "demo-skill"
    assert "olá" in preview.steps[1]
    assert "nenhum código" in preview.message.lower() or "DRY-RUN" in preview.message


def test_command_pipeline_install_custom() -> None:
    class Dummy:
        layer = Layer.MEMORY
        name = "dummy"

        def register(self, app: App) -> None:
            def _mem(a: App, _args: list[str]) -> int:
                a.stdout.write("mem-ok\n")
                return 0

            app.register_command("mem", _mem)

    out = io.StringIO()
    app = App(settings=load_settings(), stdout=out, stderr=io.StringIO())
    CommandPipeline().add(Dummy()).install(app)
    assert app.dispatch(["mem"]) == 0
    assert "mem-ok" in out.getvalue()
