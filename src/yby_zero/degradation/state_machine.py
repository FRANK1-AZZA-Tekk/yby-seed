from enum import StrEnum


class DegradationState(StrEnum):
    FULL_LOCAL = "FULL_LOCAL"
    MOBILE_LOCAL = "MOBILE_LOCAL"
    DETERMINISTIC_ONLY = "DETERMINISTIC_ONLY"
    WATCH_SAFE_MODE = "WATCH_SAFE_MODE"
    LOCKED_SAFE_STATE = "LOCKED_SAFE_STATE"


class DegradationStateMachine:
    def __init__(self) -> None:
        self.state = DegradationState.FULL_LOCAL

    def set_state(self, state: DegradationState) -> DegradationState:
        self.state = state
        return self.state

    def capabilities(self) -> set[str]:
        capabilities = {
            DegradationState.FULL_LOCAL: {
                "conversation",
                "memory",
                "rag",
                "tools",
                "voice",
            },
            DegradationState.MOBILE_LOCAL: {
                "conversation_short",
                "status",
                "voice",
            },
            DegradationState.DETERMINISTIC_ONLY: {
                "status",
                "cancel",
                "confirm",
            },
            DegradationState.WATCH_SAFE_MODE: {
                "status",
                "vibration",
                "confirm",
            },
            DegradationState.LOCKED_SAFE_STATE: {
                "diagnostics",
            },
        }
        return capabilities[self.state]
