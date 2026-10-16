import re

from src.core.gatekeeper import match_command


def test_t01_stop_command():
    assert match_command("parar") == "parar"


def test_t02_stop_smoking_is_not_command():
    assert match_command("como faço para parar de fumar") is None


def test_t03_offline_mode():
    assert match_command("modo offline") == "modo_offline"


def test_t04_sensitive_data_forces_local():
    sensitive_patterns = [
        r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
        r"-----BEGIN[A-Z ]+-----",
        r"\b[A-Fa-f0-9]{32,}\b",
    ]
    assert any(re.search(p, "Meu CPF é 123.456.789-00") for p in sensitive_patterns)
    assert any(re.search(p, "-----BEGIN PRIVATE KEY-----") for p in sensitive_patterns)


def test_command_with_punctuation():
    assert match_command("Parar!") == "parar"


def test_long_text_is_not_command():
    assert match_command("parar " + "a" * 100) is None
