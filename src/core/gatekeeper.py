import re
import unicodedata

COMMANDS = {
    r"^(?:parar|cancelar)[.!]?$": "parar",
    r"^modo\s+offline[.!]?$": "modo_offline",
    r"^modo\s+privado[.!]?$": "modo_privado",
    r"^n[ãa]o\s+use\s+a\s+nuvem[.!]?$": "sem_nuvem_sessao",
    r"^(?:qual\s+(?:o|é|e)\s+o?\s*)?custo\s+(?:de\s+)?hoje\??$": "consulta_custo",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"[\u200b-\u200f]", "", text)


def match_command(text: str):
    normalized = normalize(text)
    if len(normalized) > 60:
        return None
    for pattern, command in COMMANDS.items():
        if re.fullmatch(pattern, normalized):
            return command
    return None
