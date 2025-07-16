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
    # List event
    def list_event(self, 
                    timeMin: Optional[str] = None,
                    timeMax: Optional[str] = None,
                    json_input: str= None) -> List[dict]: 
        try:
            if timeMin and timeMax:
                # Nếu đã cung cấp timeMin và timeMax, sử dụng chúng (không chỉnh sửa gì thêm)
                pass
            # Nếu không có timeMin và timeMax, lấy từ JSON input hoặc mặc định
            elif json_input and isinstance(json_input, dict):
                # Nếu json_input là dict, lấy timeMin và timeMax từ đó
                if json_input['parameters'].get('start') is not None:
                    timeMin = json_input['parameters']['start']['dateTime']
                    timeMax = json_input['parameters']['end']['dateTime']
                else:
                    timeMin = json_input["parameters"].get("timeMin", None)
                    timeMax = json_input["parameters"].get("timeMax", None)
            # Nếu không có json_input, sử dụng thời gian hiện tại và 2 tuần sau 
            else:
                timeMin = datetime.now().isoformat()
                timeMax = (datetime.now() + timedelta(weeks=2)).isoformat()        
            # Đảm bảo timeMin và timeMax có timezone
            if not timeMin.endswith('Z') and not '+' in timeMin:
                timeMin = dateutil.parser.isoparse(timeMin).replace(tzinfo=timezone.utc).isoformat()
            if not timeMax.endswith('Z') and not '+' in timeMax:
                timeMax = dateutil.parser.isoparse(timeMax).replace(tzinfo=timezone.utc).isoformat()

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
            
            if not events:
                return f"📅 There is no schedule from {time_min_str} to {time_max_str}.", False
            else:
                output = f"📅 Schedule list from {time_min_str} to {time_max_str}:\n\n"
                for idx, event in enumerate(events):
                    # Parse thời gian
                    start_dt = dateutil.parser.isoparse(event['start'].get('dateTime', event['start'].get('date')))
                    end_dt = dateutil.parser.isoparse(event['end'].get('dateTime', event['end'].get('date')))
                    
                    # Format thời gian
                    start_str = start_dt.strftime("%d/%m/%Y %H:%M")
                    end_str = end_dt.strftime("%d/%m/%Y %H:%M")
                    
                    # Lấy thông tin sự kiện
                    summary = event.get('summary', '')
                    location = event.get('location', '')
                    
                    # Format output cho từng sự kiện
                    output +=  f"Event {idx+1}:{summary}\n\n"
                    output += f"Duration: {start_str} - {end_str}\n\n"
                    if location != "":
                        output += f"Location: {location}\n\n"
                    output += "---\n\n"
                
                return output, True

        except HttpError as e:
            print(f"Error listing events: {e}")
            return "❌ Error in listing events", False
    # Insert event
    def insert_event(self, json_input):
        event = self.extract_event_data(json_input)
        # Extract event data from JSON input
        timeMin = json_input['parameters']['start']['dateTime']
        timeMax = json_input['parameters']['end']['dateTime']
        
        # Get recurrence rule if exists
        recurrence = json_input['parameters'].get('recurrence', [])
        if recurrence and len(recurrence) > 0:
            # Parse RRULE to get days of week
            try:
                rrule = recurrence[0].split(':')[1]
            except (IndexError, AttributeError) as e:
                print(f"Error parsing recurrence rule '{recurrence[0]}': {e}")
                # Fallback to non-recurring event
                note, existed_event = self.list_event(json_input=json_input)
                if existed_event==True:
                    return f"⚠️ Schedule conflict found:\n{note}"
                else:
                    try:
                        event = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
                        return f"✅ Event created: {event.get('htmlLink')}"
                    except HttpError as e:
                        print(f"Error inserting event: {e}")
                        return None
            
            # Safely parse RRULE to get days
            days = []
            try:
                rrule_parts = rrule.split(';')
                for part in rrule_parts:
                    if part.startswith('BYDAY='):
                        days = part.split('=')[1].split(',')
                        break
                
                # If no BYDAY found, use default (current day of week)
                if not days:
                    start_dt = dateutil.parser.isoparse(timeMin)
                    days = [start_dt.strftime('%a').upper()[:2]]
                    
            except (IndexError, AttributeError) as e:
                print(f"Error parsing RRULE '{rrule}': {e}")
                # Fallback to current day of week
                start_dt = dateutil.parser.isoparse(timeMin)
                days = [start_dt.strftime('%a').upper()[:2]]
            
            # Convert days to datetime objects
            start_dt = dateutil.parser.isoparse(timeMin)
            end_dt = dateutil.parser.isoparse(timeMax)
            duration = end_dt - start_dt
            
            # Check each day in the recurrence pattern
            conflicts = []
            successful_events = []
            
            for i in range(4):  # Check next 4 weeks
                for day in days:
                    # Calculate the date for this day
                    current_date = start_dt + timedelta(days=i*7)
                    while current_date.strftime('%a').upper()[:2] != day:
                        current_date += timedelta(days=1)
                    
                    # Create event time for this day
                    event_start = current_date.replace(
                        hour=start_dt.hour,
                        minute=start_dt.minute
                    )
                    event_end = event_start + duration
                    
                    # Check for conflicts
                    note, has_conflict = self.list_event(
                        timeMin=event_start.isoformat(),
                        timeMax=event_end.isoformat()
                    )
                    
                    if has_conflict:
                        conflicts.append({
                            'day': current_date.strftime('%A'),
                            'date': current_date.strftime('%Y-%m-%d'),
                            'time': f"{event_start.strftime('%H:%M')} - {event_end.strftime('%H:%M')}",
                            'conflict_details': note
                        })
                    else:
                        # Create single event for this day
                        single_event = event.copy()
                        single_event['start']['dateTime'] = event_start.isoformat()
                        single_event['end']['dateTime'] = event_end.isoformat()
                        single_event.pop('recurrence', None)  # Remove recurrence for single event
                        
                        try:
                            created_event = self.service.events().insert(
                                calendarId=self.calendar_id,
                                body=single_event
                            ).execute()
                            successful_events.append({
                                'day': current_date.strftime('%A'),
                                'date': current_date.strftime('%Y-%m-%d'),
                                'time': f"{event_start.strftime('%H:%M')} - {event_end.strftime('%H:%M')}",
                                'link': created_event.get('htmlLink')
                            })
                        except HttpError as e:
                            print(f"Error creating event for {current_date}: {e}")
            
            # Prepare response message
            response = ""
            if conflicts:
                response += "⚠️ Schedule conflicts found:\n"
                for conflict in conflicts:
                    response += f"- {conflict['day']} ({conflict['date']}) at {conflict['time']}\n"
                    response += f"  Conflict details: {conflict['conflict_details']}\n"
            
            if successful_events:
                response += "\n✅ Successfully created events for:\n"
                for event in successful_events:
                    response += f"- {event['day']} ({event['date']}) at {event['time']}\n"
                    response += f"  Link: {event['link']}\n"
            
            return response
            
        else:
            # Handle non-recurring event
            note, existed_event = self.list_event(json_input=json_input)
            if existed_event==True:
                return f"⚠️ Schedule conflict found:\n{note}"
            else:
                try:
                    event = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
                    return f"✅ Event created: {event.get('htmlLink')}"
                except HttpError as e:
                    print(f"Error inserting event: {e}")
                    return None
    # Get event
    def get_event(self, json_input: Optional[dict] = None) -> Optional[dict]:
        try:
            # Lấy thời gian từ JSON input
            timeMin = json_input["parameters"].get("timeMin", None)
            timeMax = json_input["parameters"].get("timeMax", None)

            # Đảm bảo timeMin và timeMax có timezone
            if not timeMin.endswith('Z') and not '+' in timeMin:
                timeMin = dateutil.parser.isoparse(timeMin).replace(tzinfo=timezone.utc).isoformat()
            if not timeMax.endswith('Z') and not '+' in timeMax:
                timeMax = dateutil.parser.isoparse(timeMax).replace(tzinfo=timezone.utc).isoformat()

            # Lấy danh sách sự kiện trong khoảng thời gian
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=timeMin,
                timeMax=timeMax,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            if not events:
                return None

            # Tạo danh sách event_id và thông tin chi tiết
            event_ids = []
            for event in events:
                event_id = event['id']
                event_ids.append(event_id)

            return event_ids

        except HttpError as e:
            print(f"Error getting events: {e}")
            return None

    def delete_event(self, event_id: Optional[str]=None,json_input: Optional[dict] = None) -> bool:
        try:
            output=""
            if event_id:
                self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
                output += "Completing delete event"
            else:
                if json_input:
                    timeMin = json_input["parameters"].get("timeMin", None)
                    timeMax = json_input["parameters"].get("timeMax", None)
                    if not timeMin.endswith('Z') and not '+' in timeMin:
                        timeMin = dateutil.parser.isoparse(timeMin).replace(tzinfo=timezone.utc).isoformat()
                    if not timeMax.endswith('Z') and not '+' in timeMax:
                        timeMax = dateutil.parser.isoparse(timeMax).replace(tzinfo=timezone.utc).isoformat()
                    events_result = self.service.events().list(
                        calendarId=self.calendar_id,
                        timeMin=timeMin,
                        timeMax=timeMax,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()

                    events = events_result.get('items', [])
                    for event in events:
                        event_id=event["id"]                    
                        self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
                    output += "Completing delete events"
                else:
                    output += "Provide events need to be deleted"
            return output
        except HttpError as e:
            print(f"Error deleting event: {e}")
    # Update event
    def update_event(self, json_input: Optional[dict] = None) -> Optional[dict]:
        try:
            output=""
            timeMin = json_input['parameters']['start']['dateTime']
            timeMax = json_input['parameters']['end']['dateTime']
            if not timeMin.endswith('Z') and not '+' in timeMin:
                timeMin = dateutil.parser.isoparse(timeMin).replace(tzinfo=timezone.utc).isoformat()
            if not timeMax.endswith('Z') and not '+' in timeMax:
                timeMax = dateutil.parser.isoparse(timeMax).replace(tzinfo=timezone.utc).isoformat()
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=timeMin,
                timeMax=timeMax,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            for event in events:
                event_id=event["id"]  
                self.delete_event(event_id=event_id)
            
            self.insert_event(json_input)
            output+= "Completing update event"
            
            return output
        except HttpError as e:
            print(f"Error updating event: {e}")
            return None

    # Delete event
    
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