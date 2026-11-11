from src.yby_zero.degradation import DegradationState, DegradationStateMachine


def test_watch_safe_mode_is_limited() -> None:
    machine = DegradationStateMachine()
    machine.set_state(DegradationState.WATCH_SAFE_MODE)
    assert machine.capabilities() == {"status", "vibration", "confirm"}
