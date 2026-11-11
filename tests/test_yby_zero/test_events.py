from src.yby_zero.events import EventBus, YBYEvent


def test_event_bus_dispatches_matching_event() -> None:
    received = []
    bus = EventBus()
    bus.subscribe("test.event", received.append)
    event = YBYEvent(source="test", event_type="test.event")
    bus.publish(event)
    assert received == [event]
