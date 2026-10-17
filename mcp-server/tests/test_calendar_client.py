import logging

from app.tools.calendar import (
    DEFAULT_TZ_NAME,
    build_calendar_service,
    create_event,
    read_events,
    delete_event,
    update_event,
)


class FakeExecutable:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeEventsResource:
    """Stands in for service.events(). Records what it was called with."""

    def __init__(self, list_items=None, get_result=None, raise_error=False):
        self._list_items = list_items if list_items is not None else []
        self._get_result = get_result
        self._raise_error = raise_error
        self.last_insert_body = None
        self.last_list_kwargs = None
        self.last_patch_body = None
        self.last_patch_event_id = None
        self.last_delete_event_id = None
        self.last_get_event_id = None

    def _boom(self):
        if self._raise_error:
            raise ConnectionError("google down")

    def insert(self, calendarId, body):
        self._boom()
        self.last_insert_body = body
        return FakeExecutable({"htmlLink": "https://calendar.google.com/event?x"})

    def list(self, **kwargs):
        self._boom()
        self.last_list_kwargs = kwargs
        return FakeExecutable({"items": self._list_items})

    def get(self, calendarId, eventId):
        self._boom()
        self.last_get_event_id = eventId
        return FakeExecutable(self._get_result or {})

    def patch(self, calendarId, eventId, body):
        self._boom()
        self.last_patch_event_id = eventId
        self.last_patch_body = body
        return FakeExecutable({"htmlLink": "https://calendar.google.com/event?x"})

    def delete(self, calendarId, eventId):
        self._boom()
        self.last_delete_event_id = eventId
        return FakeExecutable(None)


class FakeService:
    def __init__(self, events_resource):
        self._events_resource = events_resource

    def events(self):
        return self._events_resource


def make_event(event_id="evt1", summary="Marketing meeting", start="2026-08-18T09:00:00+07:00",
               end="2026-08-18T10:00:00+07:00", location=None, recurring_event_id=None):
    event = {"id": event_id, "summary": summary,
             "start": {"dateTime": start}, "end": {"dateTime": end}}
    if location:
        event["location"] = location
    if recurring_event_id:
        event["recurringEventId"] = recurring_event_id
    return event


def test_create_event_normalizes_naive_start_to_plus_seven():
    events = FakeEventsResource()
    result = create_event(FakeService(events), "Standup", "2026-08-18T09:00:00")

    assert "✅ Event created" in result
    assert events.last_insert_body["start"]["dateTime"] == "2026-08-18T09:00:00+07:00"


def test_create_event_always_sends_time_zone_for_recurrence_support():
    events = FakeEventsResource()
    create_event(FakeService(events), "Daily sync", "2026-08-18T09:00:00",
                 recurrence=["RRULE:FREQ=DAILY;COUNT=5"])

    body = events.last_insert_body
    assert body["start"]["timeZone"] == DEFAULT_TZ_NAME
    assert body["end"]["timeZone"] == DEFAULT_TZ_NAME
    assert body["recurrence"] == ["RRULE:FREQ=DAILY;COUNT=5"]


def test_create_event_preserves_explicit_offset():
    events = FakeEventsResource()
    create_event(FakeService(events), "Standup", "2026-08-18T09:00:00-03:00")

    assert events.last_insert_body["start"]["dateTime"] == "2026-08-18T09:00:00-03:00"


def test_create_event_defaults_end_to_one_hour_after_start():
    events = FakeEventsResource()
    create_event(FakeService(events), "Standup", "2026-08-18T09:00:00")

    assert events.last_insert_body["end"]["dateTime"] == "2026-08-18T10:00:00+07:00"


def test_create_event_refuses_when_slot_already_busy():
    events = FakeEventsResource(list_items=[make_event()])
    result = create_event(FakeService(events), "Standup", "2026-08-18T09:00:00")

    assert result.startswith("⚠️")
    assert "Marketing meeting" in result
    assert events.last_insert_body is None


def test_create_event_skips_conflict_check_when_disabled():
    events = FakeEventsResource(list_items=[make_event()])
    result = create_event(FakeService(events), "Standup", "2026-08-18T09:00:00",
                          check_conflict=False)

    assert result.startswith("✅")
    assert events.last_list_kwargs is None


def test_create_event_includes_optional_fields():
    events = FakeEventsResource()
    create_event(FakeService(events), "Standup", "2026-08-18T09:00:00", check_conflict=False,
                 location="Room 1", description="notes", attendees=["a@example.com"],
                 color_id="5", reminder_minutes=15)

    body = events.last_insert_body
    assert body["location"] == "Room 1"
    assert body["description"] == "notes"
    assert body["attendees"] == [{"email": "a@example.com"}]
    assert body["colorId"] == "5"
    assert body["reminders"] == {"useDefault": False,
                                 "overrides": [{"method": "popup", "minutes": 15}]}


def test_create_event_omits_optional_fields_when_not_given():
    events = FakeEventsResource()
    create_event(FakeService(events), "Standup", "2026-08-18T09:00:00", check_conflict=False)

    body = events.last_insert_body
    for field in ("location", "description", "attendees", "recurrence", "colorId", "reminders"):
        assert field not in body


def test_create_event_logs_and_returns_error_on_failure(caplog):
    events = FakeEventsResource(raise_error=True)
    with caplog.at_level(logging.ERROR):
        result = create_event(FakeService(events), "Standup", "2026-08-18T09:00:00")

    assert result.startswith("❌")
    assert "calendar_create failed" in caplog.text


def test_build_calendar_service_constructs_with_access_token(monkeypatch):
    captured = {}

    def fake_build(service_name, version, credentials):
        captured.update(name=service_name, version=version, token=credentials.token)
        return "fake-service"

    monkeypatch.setattr("app.tools.calendar.build", fake_build)

    assert build_calendar_service("tok123") == "fake-service"
    assert captured == {"name": "calendar", "version": "v3", "token": "tok123"}


def test_read_events_defaults_window_and_formats_output_with_id():
    events = FakeEventsResource(list_items=[make_event(location="Room 1")])
    result = read_events(FakeService(events))

    assert "Event 1 [id: evt1]: Marketing meeting" in result
    assert "Room 1" in result
    assert events.last_list_kwargs["timeMin"] is not None
    assert events.last_list_kwargs["timeMax"] is not None
    assert "q" not in events.last_list_kwargs


def test_read_events_marks_recurring_events_with_series_id():
    events = FakeEventsResource(list_items=[make_event(recurring_event_id="series777")])
    result = read_events(FakeService(events))

    assert "[id: evt1] [series: series777]" in result


def test_read_events_passes_q_as_free_text_search():
    events = FakeEventsResource()
    read_events(FakeService(events), q="marketing")

    assert events.last_list_kwargs["q"] == "marketing"


def test_read_events_uses_explicit_window_when_given():
    events = FakeEventsResource()
    read_events(FakeService(events), time_min="2026-08-18T00:00:00+07:00",
                time_max="2026-08-19T00:00:00+07:00")

    assert events.last_list_kwargs["timeMin"] == "2026-08-18T00:00:00+07:00"
    assert events.last_list_kwargs["timeMax"] == "2026-08-19T00:00:00+07:00"


def test_read_events_returns_no_schedule_message_when_empty():
    result = read_events(FakeService(FakeEventsResource(list_items=[])))
    assert "There is no schedule" in result


def test_read_events_logs_and_returns_error_on_failure(caplog):
    events = FakeEventsResource(raise_error=True)
    with caplog.at_level(logging.ERROR):
        result = read_events(FakeService(events))

    assert result.startswith("❌")
    assert "calendar_read failed" in caplog.text


def test_update_event_patches_only_provided_fields():
    events = FakeEventsResource()
    result = update_event(FakeService(events), "evt1", summary="New title")

    assert result.startswith("✅ Event updated")
    assert events.last_patch_event_id == "evt1"
    assert events.last_patch_body == {"summary": "New title"}
    assert events.last_get_event_id is None


def test_update_event_moving_start_preserves_original_duration():
    events = FakeEventsResource(get_result=make_event(
        start="2026-08-18T09:00:00+07:00", end="2026-08-18T11:00:00+07:00"))
    update_event(FakeService(events), "evt1", start="2026-08-19T14:00:00")

    body = events.last_patch_body
    assert body["start"]["dateTime"] == "2026-08-19T14:00:00+07:00"
    assert body["end"]["dateTime"] == "2026-08-19T16:00:00+07:00"
    assert body["start"]["timeZone"] == DEFAULT_TZ_NAME


def test_update_event_accepts_explicit_start_and_end():
    events = FakeEventsResource(get_result=make_event())
    update_event(FakeService(events), "evt1", start="2026-08-19T14:00:00",
                 end="2026-08-19T15:30:00")

    body = events.last_patch_body
    assert body["start"]["dateTime"] == "2026-08-19T14:00:00+07:00"
    assert body["end"]["dateTime"] == "2026-08-19T15:30:00+07:00"


def test_update_event_rejects_end_before_start():
    events = FakeEventsResource(get_result=make_event())
    result = update_event(FakeService(events), "evt1", start="2026-08-19T14:00:00",
                          end="2026-08-19T13:00:00")

    assert result.startswith("❌")
    assert events.last_patch_body is None


def test_update_event_rejects_new_end_before_existing_start():
    events = FakeEventsResource(get_result=make_event(
        start="2026-08-18T09:00:00+07:00", end="2026-08-18T10:00:00+07:00"))
    result = update_event(FakeService(events), "evt1", end="2026-08-18T08:00:00")

    assert result.startswith("❌")
    assert events.last_patch_body is None


def test_update_event_returns_error_when_nothing_to_update():
    events = FakeEventsResource()
    result = update_event(FakeService(events), "evt1")

    assert result.startswith("❌")
    assert events.last_patch_body is None


def test_update_event_logs_and_returns_error_on_failure(caplog):
    events = FakeEventsResource(raise_error=True)
    with caplog.at_level(logging.ERROR):
        result = update_event(FakeService(events), "evt1", summary="x")

    assert result.startswith("❌")
    assert "calendar_update failed" in caplog.text


def test_delete_event_deletes_the_given_instance():
    events = FakeEventsResource()
    result = delete_event(FakeService(events), "evt1")

    assert result.startswith("✅")
    assert events.last_delete_event_id == "evt1"
    assert events.last_get_event_id is None


def test_delete_event_series_resolves_recurring_master_id():
    events = FakeEventsResource(get_result=make_event(recurring_event_id="series777"))
    result = delete_event(FakeService(events), "evt1", scope="series")

    assert result.startswith("✅")
    assert events.last_get_event_id == "evt1"
    assert events.last_delete_event_id == "series777"


def test_delete_event_series_falls_back_to_event_id_when_not_recurring():
    events = FakeEventsResource(get_result=make_event())
    delete_event(FakeService(events), "evt1", scope="series")

    assert events.last_delete_event_id == "evt1"


def test_delete_event_logs_and_returns_error_on_failure(caplog):
    events = FakeEventsResource(raise_error=True)
    with caplog.at_level(logging.ERROR):
        result = delete_event(FakeService(events), "evt1")

    assert result.startswith("❌")
    assert "calendar_delete failed" in caplog.text


def test_update_event_handles_all_day_original_event():
    # Google returns {"date": ...} (no time, no offset) for all-day events; the
    # aware-vs-naive comparison must not blow up.
    events = FakeEventsResource(get_result={
        "id": "evt1", "summary": "Trip",
        "start": {"date": "2026-08-18"}, "end": {"date": "2026-08-19"}})
    result = update_event(FakeService(events), "evt1", end="2026-08-18T18:00:00")

    assert result.startswith("✅")
    assert events.last_patch_body["end"]["dateTime"] == "2026-08-18T18:00:00+07:00"


def test_update_event_moving_all_day_event_preserves_one_day_duration():
    events = FakeEventsResource(get_result={
        "id": "evt1", "summary": "Trip",
        "start": {"date": "2026-08-18"}, "end": {"date": "2026-08-19"}})
    update_event(FakeService(events), "evt1", start="2026-09-01T08:00:00")

    body = events.last_patch_body
    assert body["start"]["dateTime"] == "2026-09-01T08:00:00+07:00"
    assert body["end"]["dateTime"] == "2026-09-02T08:00:00+07:00"
