"""Testes offline de src/evaluation/golden_set.py (A12). Sem rede, modelo ou segredo."""

from __future__ import annotations

import pytest

from src.evaluation.golden_set import GoldenSet, Task

GOOD_BACKUP_CODE = """import shutil
import zipfile


def main():
    try:
        shutil.make_archive('backup', 'zip', '.')
        zipfile.is_zipfile('backup.zip')
    except OSError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
"""


@pytest.fixture
def golden() -> GoldenSet:
    return GoldenSet()


def _task(golden: GoldenSet, task_id: str) -> Task:
    return next(t for t in golden.tasks if t.id == task_id)


def test_loads_fifteen_unique_tasks_with_valid_difficulty(golden: GoldenSet) -> None:
    ids = [t.id for t in golden.tasks]
    assert len(ids) == 15
    assert len(set(ids)) == 15
    assert {t.difficulty for t in golden.tasks} == {"fácil", "médio", "difícil"}


def test_evaluate_unknown_task_returns_error_without_calling_agent(golden: GoldenSet) -> None:
    calls: list[str] = []

    def agent(prompt: str) -> str:
        calls.append(prompt)
        return ""

    result = golden.evaluate(agent, "nao_existe")
    assert result["success"] is False
    assert "nao_existe" in result["error"]
    assert calls == []


def test_evaluate_good_code_passes_all_criteria(golden: GoldenSet) -> None:
    task = next(t for t in golden.tasks if t.category == "backup")
    result = golden.evaluate(lambda _prompt: GOOD_BACKUP_CODE, task.id)

    assert result["success"] is True
    criteria = result["evaluation"]["criteria"]
    assert result["evaluation"]["score"] >= 0.8
    assert criteria["syntax_valid"] and criteria["has_required_imports"]
    assert criteria["has_error_handling"] and criteria["is_executable"]
    assert result["within_budget"] is True
    assert result["within_timeout"] is True


def test_evaluate_passes_task_description_to_agent(golden: GoldenSet) -> None:
    seen: list[str] = []
    task = _task(golden, "easy_01")

    def agent(prompt: str) -> str:
        seen.append(prompt)
        return "import os\n"

    golden.evaluate(agent, "easy_01")
    assert seen == [task.description]


def test_evaluate_syntax_error_fails_syntax_criterion(golden: GoldenSet) -> None:
    result = golden.evaluate(lambda _p: "def broken(:\n", "easy_01")
    assert result["evaluation"]["criteria"]["syntax_valid"] is False
    assert result["success"] is False


def test_evaluate_agent_exception_is_reported_not_raised(golden: GoldenSet) -> None:
    def agent(_prompt: str) -> str:
        raise RuntimeError("falha do agente")

    result = golden.evaluate(agent, "easy_01")
    assert result == {"success": False, "task_id": "easy_01", "error": "falha do agente"}


def test_check_helpers_cover_positive_and_negative_cases(golden: GoldenSet) -> None:
    task = _task(golden, "easy_01")  # file_operations -> os / pathlib

    assert golden._check_syntax("x = 1") is True
    assert golden._check_syntax("x = (") is False

    assert golden._check_imports("import os", task) is True
    assert golden._check_imports("print('oi')", task) is False

    assert golden._check_error_handling("try:\n    pass\nexcept Exception:\n    pass") is True
    assert golden._check_error_handling("x = 1") is False

    assert golden._check_executable("def main():\n    pass") is True
    assert golden._check_executable("import os") is True
    assert golden._check_executable("x = 1") is False


def test_check_expected_output_requires_half_of_keywords(golden: GoldenSet) -> None:
    task = Task(
        id="t",
        description="d",
        expected_output="alpha beta gamma delta",
        difficulty="fácil",
        category="api",
    )
    assert golden._check_expected_output("alpha beta", task) is True
    assert golden._check_expected_output("alpha", task) is False


def test_unknown_category_never_satisfies_required_imports(golden: GoldenSet) -> None:
    task = Task(id="t", description="d", expected_output="x", difficulty="fácil", category="inexistente")
    assert golden._check_imports("import os, json, requests", task) is False


def test_run_full_benchmark_aggregates_rates_and_groups(golden: GoldenSet) -> None:
    good_ids = {t.id for t in golden.tasks if t.category == "backup"}
    by_description = {t.description: t.id for t in golden.tasks}

    def agent(prompt: str) -> str:
        return GOOD_BACKUP_CODE if by_description[prompt] in good_ids else "x = 1\n"

    report = golden.run_full_benchmark(agent)

    assert report["total_tasks"] == 15
    assert report["successful_tasks"] == len(good_ids)
    assert report["task_completion_rate"] == pytest.approx(len(good_ids) / 15)
    assert report["average_time_seconds"] >= 0
    assert len(report["detailed_results"]) == 15

    by_category = report["results_by_category"]
    assert by_category["backup"]["rate"] == 1.0
    assert sum(g["total"] for g in by_category.values()) == 15

    by_difficulty = report["results_by_difficulty"]
    assert set(by_difficulty) == {"fácil", "médio", "difícil"}
    assert sum(g["total"] for g in by_difficulty.values()) == 15
    assert all(0.0 <= g["rate"] <= 1.0 for g in by_difficulty.values())


def test_grouping_ignores_results_for_unknown_tasks(golden: GoldenSet) -> None:
    results = [{"task_id": "fantasma", "success": True}]
    assert golden._group_by_difficulty(results) == {}
    assert golden._group_by_category(results) == {}
