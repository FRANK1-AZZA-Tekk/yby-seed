from src.security.sandbox_executor import SandboxExecutor


def test_executor_fails_closed_without_isolation_backend():
    result = SandboxExecutor().execute("print('should not run')")
    assert result["success"] is False
    assert "disabled" in result["error"].lower()
    assert result["stdout"] == ""
    assert result["exit_code"] == -1


def test_retry_api_does_not_run_untrusted_code():
    result = SandboxExecutor().execute_with_retry(
        "raise RuntimeError('must not execute')", max_retries=3
    )
    assert result["success"] is False
    assert result["stdout"] == ""
