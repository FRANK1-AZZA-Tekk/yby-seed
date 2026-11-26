"""Avaliação offline pt-BR (`scripts/eval_offline.py`): sem rede, sem nuvem, determinística."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import socket
import sys
from pathlib import Path
from typing import Any

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eval_offline.py"
DATASET = ROOT / "evals" / "ptbr_basico.json"
CATEGORIES = {
    "resposta_direta",
    "explicacao_tecnica",
    "ferramenta_segura",
    "entrada_ambigua",
    "entrada_invalida",
    "recusa_segura",
}


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("eval_offline", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ev = _load_module()


def _raw() -> dict[str, Any]:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "set.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _case(data: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(c for c in data["cases"] if c["id"] == case_id)


def _by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in report["cases"]}


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("rede proibida na avaliação offline")

    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def test_conjunto_tem_as_seis_categorias_sem_nuvem() -> None:
    cases = ev.load_cases(DATASET)

    assert {c.category for c in cases} == CATEGORIES
    assert len(cases) == 6
    assert all(c.cloud is False for c in cases)
    assert all(c.input and c.verify and c.max_prompt_chars > 0 for c in cases)


def test_conjunto_tem_ficha_de_admissao() -> None:
    dataset = ev.load_dataset(DATASET)

    assert set(dataset.admission) == {
        "problema",
        "por_que_camada_existente_nao_basta",
        "dono",
        "custo",
        "criterio_de_saida",
        "risco",
    }


def test_todos_os_casos_passam_sem_rede(no_network: None) -> None:
    report = ev.run_all(DATASET)

    assert report["totals"] == {
        "cases": 6,
        "passed": 6,
        "failed": 0,
        "cloud_calls": 0,
        "tools_executed": 1,
        "simulated_latency_ms": 1505,
    }
    cases = _by_id(report)
    assert cases["direta_01"]["calls"] == {"local": 1, "cloud": 0, "planner": 0, "runner": 0}
    assert cases["ferramenta_01"]["tools_executed"] == ["echo_json"]
    assert cases["ferramenta_01"]["calls"]["planner"] == 2
    assert cases["ambigua_01"]["tools_executed"] == []
    assert cases["invalida_01"]["tools_executed"] == []
    assert "message" in cases["invalida_01"]["error"]
    assert cases["recusa_01"]["calls"]["runner"] == 0
    assert all(c["prompt_chars"] <= c["max_prompt_chars"] for c in report["cases"])


def test_execucao_e_deterministica() -> None:
    first = json.dumps(ev.run_all(DATASET), ensure_ascii=False, sort_keys=True)
    second = json.dumps(ev.run_all(DATASET), ensure_ascii=False, sort_keys=True)

    assert first == second


def test_nao_le_ambiente_nem_chave_de_nuvem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_CLOUD_API_KEY", "nao-usar")
    monkeypatch.setenv("YBY_HEAVY_MIN_CHARS", "5")
    monkeypatch.setenv("YBY_CLOUD_MODE", "ask")

    report = ev.run_all(DATASET)

    assert report["totals"]["passed"] == 6
    assert report["totals"]["cloud_calls"] == 0


def test_resposta_sem_termo_esperado_falha(tmp_path: Path) -> None:
    data = _raw()
    _case(data, "direta_01")["fake"]["reply"] = "Uma estrutura de dados qualquer."

    result = _by_id(ev.run_all(_write(tmp_path, data)))["direta_01"]

    assert result["passed"] is False
    assert result["checks"]["contains_all"] is False


def test_resposta_longa_demais_falha(tmp_path: Path) -> None:
    data = _raw()
    _case(data, "direta_01")["fake"]["reply"] = "nó próximo " * 100

    result = _by_id(ev.run_all(_write(tmp_path, data)))["direta_01"]

    assert result["checks"]["max_reply_chars"] is False


def test_tool_esperada_errada_falha(tmp_path: Path) -> None:
    data = _raw()
    _case(data, "ferramenta_01")["expect"]["tools_executed"] = ["vault_search"]

    result = _by_id(ev.run_all(_write(tmp_path, data)))["ferramenta_01"]

    assert result["passed"] is False
    assert result["checks"]["tools_executed"] is False


def test_tool_fora_da_allowlist_vira_erro_sem_execucao(tmp_path: Path) -> None:
    data = _raw()
    case = _case(data, "ferramenta_01")
    case["fake"]["planner_replies"] = [
        '{"action":"tool","name":"shell_exec","arguments":{"cmd":"ls"}}'
    ]

    result = _by_id(ev.run_all(_write(tmp_path, data)))["ferramenta_01"]

    assert result["passed"] is False
    assert result["notes"]["status"] == "error"
    assert result["tools_executed"] == []
    assert "allowlisted" in result["error"]


def test_json_invalido_do_planner_vira_erro(tmp_path: Path) -> None:
    data = _raw()
    case = _case(data, "ambigua_01")
    case["fake"]["planner_replies"] = ["isto não é json"]

    result = _by_id(ev.run_all(_write(tmp_path, data)))["ambigua_01"]

    assert result["passed"] is False
    assert result["notes"]["status"] == "error"


def test_limite_de_contexto_estourado_falha(tmp_path: Path) -> None:
    data = _raw()
    _case(data, "direta_01")["max_prompt_chars"] = 10

    result = _by_id(ev.run_all(_write(tmp_path, data)))["direta_01"]

    assert result["checks"]["prompt_within_limit"] is False


def test_gate_com_comando_permitido_nao_conta_como_recusa(tmp_path: Path) -> None:
    data = _raw()
    _case(data, "recusa_01")["input"] = "ls"

    result = _by_id(ev.run_all(_write(tmp_path, data)))["recusa_01"]

    assert result["passed"] is False
    assert result["checks"]["decision"] is False
    assert result["notes"]["decision"] == "run"
    assert result["calls"]["runner"] == 1


def test_pedido_pesado_sem_chave_fica_local(tmp_path: Path, no_network: None) -> None:
    data = _raw()
    _case(data, "direta_01")["input"] = "Pensa mais: o que é uma lista ligada?"

    result = _by_id(ev.run_all(_write(tmp_path, data)))["direta_01"]

    assert result["passed"] is True
    assert any("frase explícita" in r for r in result["notes"]["route_reasons"])
    assert result["calls"]["cloud"] == 0
    assert result["calls"]["local"] == 1


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda d: d["cases"].append(copy.deepcopy(d["cases"][0])), id="id_duplicado"),
        pytest.param(lambda d: d["cases"][0].update(kind="shell"), id="kind_desconhecido"),
        pytest.param(lambda d: d["cases"][0].update(cloud=True), id="cloud_true"),
        pytest.param(lambda d: d["cases"][0].pop("expect"), id="sem_expect"),
        pytest.param(lambda d: d["cases"][0].pop("cloud"), id="sem_cloud"),
        pytest.param(lambda d: d["cases"][0]["expect"].pop("provider"), id="sem_criterio_do_kind"),
        pytest.param(lambda d: d["cases"][0]["expect"].update(decision="refuse"), id="criterio_de_outro_kind"),
        pytest.param(lambda d: d["cases"][0]["expect"].update(foo=1), id="chave_desconhecida"),
        pytest.param(lambda d: d["cases"][0].update(max_prompt_chars=0), id="limite_zero"),
        pytest.param(lambda d: d.update(cases=[]), id="sem_casos"),
        pytest.param(lambda d: d.update(version=2), id="versao_desconhecida"),
    ],
)
def test_conjunto_invalido_falha_ao_carregar(tmp_path: Path, mutate: Any) -> None:
    data = _raw()
    mutate(data)

    with pytest.raises(ev.EvalDatasetError):
        ev.load_cases(_write(tmp_path, data))


def test_arquivo_inexistente_falha_ao_carregar(tmp_path: Path) -> None:
    with pytest.raises(ev.EvalDatasetError):
        ev.load_cases(tmp_path / "nao-existe.json")


def test_main_resumo_e_codigo_de_saida() -> None:
    out = io.StringIO()

    assert ev.main([str(DATASET)], out=out) == 0
    lines = out.getvalue().splitlines()
    assert len(lines) == 7
    assert all(line.startswith("PASS ") for line in lines[:6])
    assert lines[-1].startswith("total: 6/6 ok, nuvem=0")


def test_main_json_parseavel() -> None:
    out = io.StringIO()

    assert ev.main(["--json", str(DATASET)], out=out) == 0
    report = json.loads(out.getvalue())
    assert report["dataset"] == "ptbr_basico"
    assert report["totals"]["failed"] == 0


def test_main_sai_1_quando_caso_falha(tmp_path: Path) -> None:
    data = _raw()
    _case(data, "tecnica_01")["fake"]["reply"] = "Depende."
    out = io.StringIO()

    assert ev.main([str(_write(tmp_path, data))], out=out) == 1
    assert "FAIL tecnica_01" in out.getvalue()


def test_main_sai_2_com_conjunto_invalido(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "ruim.json"
    path.write_text("{", encoding="utf-8")

    assert ev.main([str(path)], out=io.StringIO()) == 2
    assert "conjunto inválido" in capsys.readouterr().err
