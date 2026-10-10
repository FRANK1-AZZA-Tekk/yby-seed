from __future__ import annotations

from typing import Any


class SandboxExecutor:
    """Fail-closed placeholder; this class does not provide a security sandbox.

    Running AI-generated Python inside the application process or in a plain
    subprocess is not an isolation boundary. Execution stays disabled until a
    separately hardened container/OS sandbox is implemented and reviewed.
    """

    def __init__(self, **_: Any) -> None:
        pass

    def execute(self, code: str, input_data: str | None = None) -> dict[str, Any]:
        del code, input_data
        return {
            "success": False,
            "error": "Execution disabled: no hardened isolation backend is configured.",
            "details": "Use a reviewed container/OS sandbox with least privilege and network disabled.",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }

    def execute_with_retry(
        self, code: str, max_retries: int = 3, input_data: str | None = None
    ) -> dict[str, Any]:
        del code, max_retries, input_data
        return self.execute("")
