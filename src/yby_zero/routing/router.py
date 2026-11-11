from pydantic import BaseModel


class RoutingContext(BaseModel):
    text: str
    privacy_level: str = "P1"
    requires_vision: bool = False
    requires_tools: bool = False
    latency_target_ms: int = 2000
    pc_available: bool = True
    network_available: bool = True
    battery_percent: int = 100
    budget_mode: str = "controlled"


class RouteDecision(BaseModel):
    provider: str
    model: str | None = None
    reason: str
    allow_cloud: bool
    fallback_provider: str | None = None


class Router:
    """Roteador de provider/modelo por privacidade, latência e disponibilidade."""

    def decide(self, context: RoutingContext) -> RouteDecision:
        if context.privacy_level == "P3":
            return RouteDecision(
                provider="local_rules",
                reason="P3 exige processamento determinístico ou confirmação",
                allow_cloud=False,
                fallback_provider="safe_mode",
            )
        if context.privacy_level == "P2" and context.pc_available:
            return RouteDecision(
                provider="ollama",
                model="qwen2.5-coder:3b",
                reason="P2 prioriza processamento local no PC",
                allow_cloud=False,
                fallback_provider="mobile_local",
            )
        if context.requires_vision and context.network_available:
            return RouteDecision(
                provider="multimodal_cloud",
                reason="A solicitação requer capacidade multimodal autorizada",
                allow_cloud=True,
                fallback_provider="ollama",
            )
        if context.pc_available:
            return RouteDecision(
                provider="ollama",
                model="qwen2.5-coder:3b",
                reason="PC local disponível",
                allow_cloud=False,
                fallback_provider="mobile_local",
            )
        if context.network_available and context.budget_mode != "offline":
            return RouteDecision(
                provider="openrouter",
                reason="PC indisponível e fallback externo permitido",
                allow_cloud=True,
                fallback_provider="deterministic",
            )
        return RouteDecision(
            provider="deterministic",
            reason="Somente regras locais disponíveis",
            allow_cloud=False,
            fallback_provider="watch_safe_mode",
        )
