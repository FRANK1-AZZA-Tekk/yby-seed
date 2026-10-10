from src.security.sandbox_executor import SandboxExecutor


def test_executor_fails_closed_without_isolation_backend():
    result = SandboxExecutor().execute("print('should not run')")
    assert result["success"] is False
    assert "disabled" in result["error"].lower()
    assert result["stdout"] == ""


def test_retry_api_does_not_retry_untrusted_code():
    result = SandboxExecutor().execute_with_retry("print('should not run')", max_retries=3)
    assert result["success"] is False
