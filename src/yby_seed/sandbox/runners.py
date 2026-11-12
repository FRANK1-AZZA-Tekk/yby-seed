"""Runners Docker especializados (Python / C++ embarcado)."""

from __future__ import annotations

import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from src.yby_seed.config import Settings


@dataclass(frozen=True)
class RunnerCommand:
    image: str
    shell_cmd: str
    extra_files: dict[str, str]


class BaseRunner(ABC):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def build(self, work: Path, code: str, filename: str, tests: str | None) -> RunnerCommand:
        raise NotImplementedError


class PythonRunner(BaseRunner):
    """Ruff + compileall (tipagem estrutural básica) + pytest."""

    def build(self, work: Path, code: str, filename: str, tests: str | None) -> RunnerCommand:
        target = work / (filename or "main.py")
        target.write_text(code, encoding="utf-8")
        test_body = tests or "def test_smoke():\n    assert True\n"
        (work / "test_generated.py").write_text(test_body, encoding="utf-8")
        shell_cmd = "ruff check . && python3 -m compileall -q . && pytest -q"
        return RunnerCommand(
            image=self.settings.sandbox_python_image,
            shell_cmd=shell_cmd,
            extra_files={},
        )


class EmbeddedCppRunner(BaseRunner):
    """Includes ESP-IDF/LVGL, g++ -fsyntax-only com headers stub leves."""

    def build(self, work: Path, code: str, filename: str, tests: str | None) -> RunnerCommand:
        cpp_name = filename if filename.endswith(".cpp") else "firmware.cpp"
        (work / cpp_name).write_text(code, encoding="utf-8")

        stubs = _embedded_stub_tree()
        for rel, content in stubs.items():
            path = work / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        lint_script = work / "embedded_lint.py"
        lint_script.write_text(_embedded_lint_script(), encoding="utf-8")

        shell_cmd = (
            f"python3 embedded_lint.py {cpp_name} && "
            "g++ -std=c++17 -fsyntax-only -Werror "
            "-Istubs/esp_idf -Istubs/lvgl "
            f"-c {cpp_name}"
        )
        return RunnerCommand(
            image=self.settings.sandbox_cpp_image,
            shell_cmd=shell_cmd,
            extra_files=stubs,
        )


def _embedded_stub_tree() -> dict[str, str]:
    return {
        "stubs/esp_idf/esp_log.h": "#pragma once\n#define ESP_LOGI(tag, fmt, ...) ((void)0)\n",
        "stubs/esp_idf/driver/gpio.h": "#pragma once\ntypedef int gpio_num_t;\n",
        "stubs/esp_idf/freertos/FreeRTOS.h": "#pragma once\n",
        "stubs/lvgl/lvgl.h": "#pragma once\ntypedef struct _lv_obj_t lv_obj_t;\n",
        "stubs/lvgl/lv_conf.h": "#pragma once\n",
    }


def _embedded_lint_script() -> str:
    return (
        textwrap.dedent(
            """
        import re, sys
        code = open(sys.argv[1], encoding="utf-8").read()
        issues = []
        if "esp_idf" in code.lower() or "esp_log" in code:
            required = ["esp_log.h"]
            for header in required:
                if header not in code:
                    issues.append(f"include ESP-IDF ausente: {header}")
        if "lvgl" in code.lower() or "lv_obj" in code:
            if "lvgl.h" not in code:
                issues.append("include LVGL v9 ausente: lvgl.h")
        duplicates = {}
        for m in re.finditer(r"#include\\s+[<\\"]([^>\\"]+)[>\\"]", code):
            header = m.group(1)
            duplicates[header] = duplicates.get(header, 0) + 1
        for header, count in duplicates.items():
            if count > 1:
                issues.append(f"include duplicado: {header}")
        if issues:
            print("\\n".join(issues))
            sys.exit(1)
        print("embedded structure ok")
        """
        ).strip()
        + "\n"
    )


def select_runner(language: str, settings: Settings) -> BaseRunner:
    if language == "python":
        return PythonRunner(settings)
    if language == "cpp_embedded":
        return EmbeddedCppRunner(settings)
    raise ValueError(f"runner indisponível para linguagem: {language}")
