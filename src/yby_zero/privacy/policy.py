from pydantic import BaseModel


class PrivacyDecision(BaseModel):
    level: str
    allow_local: bool
    allow_cloud: bool
    redact_before_cloud: bool
    require_confirmation: bool
    reason: str


class PrivacyPolicy:
    def classify(self, level: str) -> PrivacyDecision:
        if level == "P3":
            return PrivacyDecision(
                level=level,
                allow_local=True,
                allow_cloud=False,
                redact_before_cloud=True,
                require_confirmation=True,
                reason="Dados ou ações críticas",
            )
        if level == "P2":
            return PrivacyDecision(
                level=level,
                allow_local=True,
                allow_cloud=False,
                redact_before_cloud=True,
                require_confirmation=False,
                reason="Dados sensíveis permanecem locais",
            )
        if level == "P0":
            return PrivacyDecision(
                level=level,
                allow_local=True,
                allow_cloud=True,
                redact_before_cloud=False,
                require_confirmation=False,
                reason="Conteúdo público; qualquer provider permitido",
            )
        return PrivacyDecision(
            level=level or "P1",
            allow_local=True,
            allow_cloud=True,
            redact_before_cloud=False,
            require_confirmation=False,
            reason="Processamento externo permitido pela política inicial",
        )
