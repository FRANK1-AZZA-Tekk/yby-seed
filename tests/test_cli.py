"""Testes da CLI do YBY SEED."""

from unittest.mock import patch

from click.testing import CliRunner

from src.main import cli


runner = CliRunner()


def test_test_command_runs_pytest():
    with patch("src.main.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = runner.invoke(cli, ["test"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        assert command[1:3] == ["-m", "pytest"]


def test_test_command_propagates_pytest_failure():
    with patch("src.main.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 2
        result = runner.invoke(cli, ["test"])
        assert result.exit_code == 2


def test_run_command_fails_clearly():
    result = runner.invoke(cli, ["run"])
    assert result.exit_code == 1


def test_setup_command_fails_clearly():
    result = runner.invoke(cli, ["setup"])
    assert result.exit_code == 1
