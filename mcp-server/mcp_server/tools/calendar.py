import logging
from datetime import datetime, timedelta, timezone

import dateutil.parser
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

DEFAULT_TZ = timezone(timedelta(hours=7))
DEFAULT_TZ_NAME = "Asia/Ho_Chi_Minh"
CALENDAR_ID = "primary"


def build_calendar_service(access_token: str):
    """Build a throwaway Calendar client. No caching, no refresh — the backend owns both."""
    return build("calendar", "v3", credentials=Credentials(token=access_token))


def _normalize_datetime(value: str) -> str:
    dt = dateutil.parser.isoparse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DEFAULT_TZ)
    return dt.isoformat()


def _time_field(iso_value: str) -> dict:
    # timeZone is mandatory for Google to expand an RRULE; always send it.
    return {"dateTime": iso_value, "timeZone": DEFAULT_TZ_NAME}


def _shift(iso_value: str, delta: timedelta) -> str:
    return (dateutil.parser.isoparse(iso_value) + delta).isoformat()


def _list_events(service, time_min: str, time_max: str, q: str | None = None) -> list[dict]:
    kwargs = {
        "calendarId": CALENDAR_ID,
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if q:
        kwargs["q"] = q
    return service.events().list(**kwargs).execute().get("items", [])


def _format_events(events: list[dict], time_min: str, time_max: str) -> str:
    time_min_str = dateutil.parser.isoparse(time_min).strftime("%d/%m/%Y %H:%M")
    time_max_str = dateutil.parser.isoparse(time_max).strftime("%d/%m/%Y %H:%M")

    if not events:
        return f"📅 There is no schedule from {time_min_str} to {time_max_str}."

    output = f"📅 Schedule list from {time_min_str} to {time_max_str}:\n\n"
    for idx, event in enumerate(events, start=1):
        start_raw = event["start"].get("dateTime", event["start"].get("date"))
        end_raw = event["end"].get("dateTime", event["end"].get("date"))
        start_str = dateutil.parser.isoparse(start_raw).strftime("%d/%m/%Y %H:%M")
        end_str = dateutil.parser.isoparse(end_raw).strftime("%d/%m/%Y %H:%M")

        series = event.get("recurringEventId")
        series_tag = f" [series: {series}]" if series else ""

        output += f"Event {idx} [id: {event['id']}]{series_tag}: {event.get('summary', '')}\n"
        output += f"Duration: {start_str} - {end_str}\n"
        if event.get("location"):
            output += f"Location: {event['location']}\n"
        output += "---\n"
    return output


def create_event(
    service,
    summary: str,
    start: str,
    end: str | None = None,
    location: str | None = None,
    description: str | None = None,
    attendees: list[str] | None = None,
    recurrence: list[str] | None = None,
    color_id: str | None = None,
    reminder_minutes: int | None = None,
    check_conflict: bool = True,
) -> str:
    try:
        start_iso = _normalize_datetime(start)
        end_iso = _normalize_datetime(end) if end else _shift(start_iso, timedelta(hours=1))

        if check_conflict:
            # For a recurring event this only checks the first occurrence — expanding the
            # RRULE client-side is what made the old implementation slow and fragile.
            clashes = _list_events(service, start_iso, end_iso)
            if clashes:
                return "⚠️ Khung giờ này đã có lịch:\n" + _format_events(clashes, start_iso, end_iso)

        body: dict = {
            "summary": summary,
            "start": _time_field(start_iso),
            "end": _time_field(end_iso),
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": email} for email in attendees]
        if recurrence:
            body["recurrence"] = recurrence
        if color_id:
            body["colorId"] = color_id
        if reminder_minutes is not None:
            body["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": reminder_minutes}],
            }

        created = service.events().insert(calendarId=CALENDAR_ID, body=body).execute()
        return f"✅ Event created: {created.get('htmlLink')}"
    except Exception:
        logger.exception("calendar_create failed for summary=%r start=%r", summary, start)
        return "❌ Không thể tạo lịch: đã xảy ra lỗi hệ thống."


def read_events(
    service,
    time_min: str | None = None,
    time_max: str | None = None,
    q: str | None = None,
) -> str:
    try:
        now = datetime.now(DEFAULT_TZ)
        start_iso = _normalize_datetime(time_min) if time_min else now.isoformat()
        end_iso = _normalize_datetime(time_max) if time_max else (now + timedelta(weeks=2)).isoformat()

        events = _list_events(service, start_iso, end_iso, q=q)
        return _format_events(events, start_iso, end_iso)
    except Exception:
        logger.exception("calendar_read failed for q=%r", q)
        return "\u274c Kh\u00f4ng th\u1ec3 \u0111\u1ecdc l\u1ecbch: \u0111\u00e3 x\u1ea3y ra l\u1ed7i h\u1ec7 th\u1ed1ng."


def update_event(
    service,
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> str:
    try:
        body: dict = {}
        if summary is not None:
            body["summary"] = summary
        if location is not None:
            body["location"] = location
        if description is not None:
            body["description"] = description

        if start is not None or end is not None:
            existing = service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
            # All-day events come back as {"date": ...} and parse naive; give them the
            # default zone so comparisons against normalized (aware) values work.
            old_start = dateutil.parser.isoparse(
                _normalize_datetime(existing["start"].get("dateTime", existing["start"].get("date")))
            )
            old_end = dateutil.parser.isoparse(
                _normalize_datetime(existing["end"].get("dateTime", existing["end"].get("date")))
            )

            if start is not None and end is None:
                # Moving an event keeps how long it lasts; patching start alone would
                # leave Google holding the old end, which can invert the interval.
                new_start = _normalize_datetime(start)
                body["start"] = _time_field(new_start)
                body["end"] = _time_field(_shift(new_start, old_end - old_start))
            elif start is None and end is not None:
                new_end = _normalize_datetime(end)
                if dateutil.parser.isoparse(new_end) <= old_start:
                    return "❌ Không thể cập nhật: thời gian kết thúc phải sau thời gian bắt đầu."
                body["end"] = _time_field(new_end)
            else:
                new_start = _normalize_datetime(start)
                new_end = _normalize_datetime(end)
                if dateutil.parser.isoparse(new_end) <= dateutil.parser.isoparse(new_start):
                    return "❌ Không thể cập nhật: thời gian kết thúc phải sau thời gian bắt đầu."
                body["start"] = _time_field(new_start)
                body["end"] = _time_field(new_end)

        if not body:
            return "❌ Không có thông tin nào để cập nhật."

        updated = service.events().patch(
            calendarId=CALENDAR_ID, eventId=event_id, body=body
        ).execute()
        return f"✅ Event updated: {updated.get('htmlLink')}"
    except Exception:
        logger.exception("calendar_update failed for event_id=%r", event_id)
        return f"❌ Không thể cập nhật lịch (id: {event_id}): đã xảy ra lỗi hệ thống."


def delete_event(service, event_id: str, scope: str = "instance") -> str:
    try:
        target_id = event_id
        if scope == "series":
            # calendar_read lists with singleEvents=True, so the ids it hands the planner
            # are instance ids; the master id is what deletes the whole series.
            existing = service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
            target_id = existing.get("recurringEventId") or event_id

        service.events().delete(calendarId=CALENDAR_ID, eventId=target_id).execute()

        if scope == "series":
            return f"✅ Đã xóa toàn bộ chuỗi lịch lặp (id: {target_id})"
        return f"✅ Đã xóa lịch (id: {target_id})"
    except Exception:
        logger.exception("calendar_delete failed for event_id=%r scope=%r", event_id, scope)
        return f"❌ Không thể xóa lịch (id: {event_id}): đã xảy ra lỗi hệ thống."
