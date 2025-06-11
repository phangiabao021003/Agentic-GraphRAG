from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import dateutil.parser
from calendar_tool.auth import get_calendar_credentials


# Google Calendar API
class GoogleCalendar:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(GoogleCalendar, cls).__new__(cls)
        return cls._instance

    def __init__(self, calendar_id: str = 'primary'):
        if not self._initialized:
            # Get credentials
            creds = get_calendar_credentials()

            # Build the Google Calendar API service 
            self.service = build('calendar', 'v3', credentials=creds)
            self.calendar_id = calendar_id
            self._initialized = True

    def __enter__(self):
        return self

    def __exit__(self):
        if self.service:
            self.service.close()
    def extract_event_data(self,json):        
        parameters = json.get('parameters', {})

        # Tạo một event với các trường có sẵn trong 'parameters', nếu không có thì gán giá trị rỗng
        extracted_events = {
            'summary': parameters.get('summary', ''),
            'location': parameters.get('location', ''),
            'description': parameters.get('description', ''),
            'start': {
                'dateTime': parameters.get('start', {}).get('dateTime', ''),
                'timeZone': parameters.get('start', {}).get('timeZone', ''),
            },
            'end': {
                'dateTime': parameters.get('end', {}).get('dateTime', ''),
                'timeZone': parameters.get('end', {}).get('timeZone', ''),
            },
            'recurrence': parameters.get('recurrence', []),
            'attendees': parameters.get('attendees', []),  # Trường này có thể không có trong JSON gốc
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': reminder['method'], 'minutes': reminder['minutes']}
                    for reminder in json.get('metadata', {}).get('defaultReminders', [])
                ],
            },
        }

        return extracted_events
    # Insert event
    def insert_event(self, json_input):

        start_time = event[0]['parameters']['start']['dateTime']
        end_time = event[0]['parameters']['end']['dateTime']
        note,existed_event = self.list_event(timeMin=start_time, timeMax=end_time)
        if existed_event == True:
            noti= "There is already an event in this time slot."
            return noti
        else:
            try:
                event = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
                noti= f"Event created: {event.get('htmlLink')}"
                return noti
            except HttpError as e:
                print(f"Error inserting event: {e}")
                return None


    # List event
    def list_event(self, timeMin: Optional[str] = None, timeMax: Optional[str] = None, json_input: Optional[dict] = None) -> List[dict]: 
        try:
            # Nếu không có timeMin hoặc timeMax, lấy mặc định từ JSON input nếu có
            if not timeMin or not timeMax:
                if json_input:
                    timeMin = json_input["parameters"].get("timeMin", None)  # Lấy timeMin từ JSON nếu có
                    timeMax = json_input["parameters"].get("timeMax", None)  # Lấy timeMax từ JSON nếu có

                if not timeMin or not timeMax:
                    timeMin = datetime.now().isoformat()
                    timeMax = (datetime.now() + timedelta(weeks=2)).isoformat()

            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=timeMin,  # Thời gian bắt đầu từ timeMin
                timeMax=timeMax,  # Thời gian kết thúc đến timeMax
                singleEvents=True,
                orderBy='startTime',  # Sắp xếp theo thời gian bắt đầu
            ).execute()

            events = events_result.get('items', [])
            dt_min = dateutil.parser.isoparse(timeMin)
            dt_max = dateutil.parser.isoparse(timeMax)

            # Format lại chuỗi thời gian theo định dạng dd/mm/yyyy HH:MM
            time_min_str = dt_min.strftime("%d/%m/%Y %H:%M")
            time_max_str = dt_max.strftime("%d/%m/%Y %H:%M")
            output = ""
            if not events:
                output += f"There is no schedule from {time_min_str} to {time_max_str}."
                return output, False
            else:
                output += f"Events since {timeMin} to {timeMax}:"
                for event in events:
                    summary = event.get('summary', 'No summary')
                    start = event['start'].get('dateTime', event['start'].get('date', 'There is no start time'))
                    end = event['end'].get('dateTime', event['end'].get('date', 'There is no end time'))
                    location = event.get('location', 'No mentioned location')
                    output += f"Summary: {summary}\n"
                    output += f"Start time: {start}\n"
                    output += f"End time: {end}\n"
                    output += f"Location: {location}\n"
                    output += "-" * 50 + "\n"
                return output, True

        except HttpError as e:
            print(f"Error listing events: {e}")
            return []

    # Get event
    def get_event(self, event_id: str) -> Optional[dict]:
        try:
            event = self.service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()
            return event
        except HttpError as e:
            print(f"Error getting event: {e}")
            return None

    # Update event
    def update_event(self, event_id: str, event: dict) -> Optional[dict]:
        try:
            body = self.get_event(event_id)

            # Update the event
            for key, value in event.items():
                body[key] = value

            event = self.service.events().update(calendarId=self.calendar_id, eventId=event_id, body=body).execute()
            return event
        except HttpError as e:
            print(f"Error updating event: {e}")
            return None

    # Delete event
    def delete_event(self, event_id: str) -> bool:
        try:
            if self.get_event(event_id)['status'] == 'cancelled':
                return False
            
            self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
            return True
        except HttpError as e:
            print(f"Error deleting event: {e}")
            return False

    def query_free_busy(self, timeMin: Optional[str] = None, timeMax: Optional[str] = None, items: Optional[List[str]] = None) -> List[dict]:
        try:
            # Default values if not provided
            if not timeMin:
                timeMin = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            if not timeMax:
                timeMax = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
            if not items:
                items = [{"id": "primary"}]

            body = {
                "timeMin": timeMin,
                "timeMax": timeMax,
                "items": items
            }

            free_busy = self.service.freebusy().query(body=body).execute()
            return free_busy
        
        except HttpError as e:
            print(f"Error querying free busy: {e}")
            return []