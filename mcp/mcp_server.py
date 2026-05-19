#!/usr/bin/env python3
"""MCP server for holiday booking (mock implementation)."""
import base64
import uuid
from datetime import date

from fastmcp import FastMCP
from fastmcp.server.auth import JWTVerifier
from fastmcp.server.middleware import Middleware, MiddlewareContext

""""class LoggingMiddleware(Middleware):
    async def on_message(self, message, context, next_handler):
        # Log the incoming request
        print(f">>> REQUEST: {json.dumps(message, indent=2, default=str)}")

        # Call the next handler and get response
        response = await next_handler(message)

        # Log the response
        print(f"<<< RESPONSE: {json.dumps(response, indent=2, default=str)}")

        return response
"""


class VerboseLoggingMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        print("=" * 80)
        print(">>> REQUEST")
        print(f"    Method:    {context.method}")
        print(f"    Source:    {getattr(context, 'source', 'N/A')}")
        print(f"    Session:   {getattr(context, 'session_id', 'N/A')}")

        # Message type and full payload
        msg = context.message
        print(f"    Type:      {type(msg).__name__}")
        if hasattr(msg, "model_dump"):
            print("    Payload:")
            print(json.dumps(msg.model_dump(), indent=4, default=str))
        else:
            print(f"    Payload:   {msg}")

        # Request metadata / headers if available
        request = getattr(context, "request", None)
        if request is not None:
            print(f"    Request Type: {type(request).__name__}")
            if hasattr(request, "headers"):
                print("    Headers:")
                for k, v in request.headers.items():
                    print(f"        {k}: {v}")
            if hasattr(request, "url"):
                print(f"    URL:       {request.url}")
            if hasattr(request, "method"):
                print(f"    HTTP Method: {request.method}")

        # Dump all context attributes for discovery
        print(f"    Context attrs: {[a for a in dir(context) if not a.startswith('_')]}")

        print("-" * 80)

        result = await call_next(context)

        print("<<< RESPONSE")
        print(f"    Method:    {context.method}")
        if result is not None:
            print(f"    Type:      {type(result).__name__}")
            if hasattr(result, "model_dump"):
                print("    Payload:")
                print(json.dumps(result.model_dump(), indent=4, default=str))
            elif isinstance(result, (dict, list)):
                print("    Payload:")
                print(json.dumps(result, indent=4, default=str))
            else:
                print(f"    Payload:   {result}")
        else:
            print("    Payload:   None")

        print("=" * 80)
        return result


# Configure JWT verification

ENABLE_JWT_VERIFIER = False

if ENABLE_JWT_VERIFIER:
    verifier = JWTVerifier(
        public_key=base64.b64decode("RmFiYTg4ODghISFMb2xBbGVuYUZhYmlvTWF0ZXVzelRlc3Q="),
        issuer="https://fabidemoclouddevel.sq.fabasoft.com/folio",
        audience="ai-python-service",
        algorithm="HS256",
    )
    mcp = FastMCP("Holiday/Email/Calendar Booking Server", auth=verifier)
else:
    mcp = FastMCP(
        "Holiday/Email/Calendar Booking Server",
        # middleware=[VerboseLoggingMiddleware()],
    )

HOLIDAYS = [
    {
        "id": "H001",
        "destination": "Maldives",
        "duration_days": 7,
        "price_usd": 2500,
        "available_from": "2026-05-01",
        "available_to": "2026-09-30",
    },
    {
        "id": "H002",
        "destination": "Bali, Indonesia",
        "duration_days": 10,
        "price_usd": 1800,
        "available_from": "2026-04-01",
        "available_to": "2026-12-31",
    },
    {
        "id": "H003",
        "destination": "Santorini, Greece",
        "duration_days": 5,
        "price_usd": 3200,
        "available_from": "2026-06-01",
        "available_to": "2026-10-15",
    },
    {
        "id": "H004",
        "destination": "Kyoto, Japan",
        "duration_days": 8,
        "price_usd": 2100,
        "available_from": "2026-03-15",
        "available_to": "2026-11-30",
    },
    {
        "id": "H005",
        "destination": "Patagonia, Argentina",
        "duration_days": 12,
        "price_usd": 4000,
        "available_from": "2026-11-01",
        "available_to": "2027-03-31",
    },
]

# In-memory bookings store
_bookings: dict[str, dict] = {}


@mcp.tool()
def list_holidays(destination_filter: str = "") -> str:
    """List all available holiday packages, optionally filtered by destination keyword."""
    results = HOLIDAYS
    if destination_filter:
        results = [h for h in HOLIDAYS if destination_filter.lower() in h["destination"].lower()]
    if not results:
        return "No holidays found matching your filter."
    return json.dumps(results, indent=2)


@mcp.tool()
def get_holiday_details(holiday_id: str) -> str:
    """Get detailed information about a specific holiday package by its ID."""
    holiday = next((h for h in HOLIDAYS if h["id"] == holiday_id), None)
    if not holiday:
        return f"Holiday '{holiday_id}' not found."
    return json.dumps(holiday, indent=2)


@mcp.tool()
def book_holiday(holiday_id: str, traveller_name: str, start_date: str, num_travellers: int = 1) -> str:
    """
    Book a holiday package.

    Args:
        holiday_id: The ID of the holiday to book (e.g. H001).
        traveller_name: Full name of the lead traveller.
        start_date: Desired start date in YYYY-MM-DD format.
        num_travellers: Number of travellers (default 1).
    """
    holiday = next((h for h in HOLIDAYS if h["id"] == holiday_id), None)
    if not holiday:
        return f"Error: Holiday '{holiday_id}' not found."

    try:
        parsed = date.fromisoformat(start_date)
        avail_from = date.fromisoformat(holiday["available_from"])
        avail_to = date.fromisoformat(holiday["available_to"])
    except ValueError:
        return "Error: start_date must be in YYYY-MM-DD format."

    if not (avail_from <= parsed <= avail_to):
        return (
            f"Error: '{start_date}' is outside the available window "
            f"({holiday['available_from']} – {holiday['available_to']})."
        )

    if num_travellers < 1:
        return "Error: num_travellers must be at least 1."

    booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"
    total_price = holiday["price_usd"] * num_travellers

    booking = {
        "booking_id": booking_id,
        "holiday_id": holiday_id,
        "destination": holiday["destination"],
        "traveller_name": traveller_name,
        "num_travellers": num_travellers,
        "start_date": start_date,
        "duration_days": holiday["duration_days"],
        "total_price_usd": total_price,
        "status": "confirmed",
    }
    _bookings[booking_id] = booking

    return json.dumps({"message": "Booking confirmed!", "booking": booking}, indent=2)


@mcp.tool()
def list_bookings(traveller_name: str = "") -> str:
    """
    List all bookings, optionally filtered by traveller name.

    Args:
        traveller_name: Filter bookings by lead traveller name (case-insensitive, partial match).
    """
    bookings = list(_bookings.values())
    if traveller_name:
        bookings = [b for b in bookings if traveller_name.lower() in b["traveller_name"].lower()]
    if not bookings:
        return "No bookings found."
    return json.dumps(bookings, indent=2)


@mcp.tool()
def cancel_booking(booking_id: str) -> str:
    """Cancel an existing booking by its booking ID."""
    booking = _bookings.get(booking_id)
    if not booking:
        return f"Error: Booking '{booking_id}' not found."
    if booking["status"] == "cancelled":
        return f"Booking '{booking_id}' is already cancelled."
    booking["status"] = "cancelled"
    return json.dumps({"message": f"Booking '{booking_id}' has been cancelled.", "booking": booking}, indent=2)


import json
from datetime import datetime

# Mock data storage
_emails = {}
_email_counter = 1
_calendar_events = {}
_event_counter = 1

# Initialize with some mock data
_emails = {
    1: {
        "id": 1,
        "from": "john.doe@example.com",
        "to": "user@example.com",
        "subject": "Meeting Tomorrow",
        "body": "Don't forget about our meeting at 10 AM.",
        "timestamp": "2026-04-23T14:30:00",
        "read": False,
    },
    2: {
        "id": 2,
        "from": "jane.smith@example.com",
        "to": "user@example.com",
        "subject": "Project Update",
        "body": "The Q2 report is ready for review.",
        "timestamp": "2026-04-24T09:15:00",
        "read": True,
    },
    3: {
        "id": 3,
        "from": "support@service.com",
        "to": "user@example.com",
        "subject": "Your Order #12345",
        "body": "Your order has been shipped and will arrive in 2-3 business days.",
        "timestamp": "2026-04-24T11:45:00",
        "read": False,
    },
}
_email_counter = 4

_calendar_events = {
    1: {
        "id": 1,
        "title": "Team Standup",
        "description": "Daily team sync",
        "start_time": "2026-04-25T09:00:00",
        "end_time": "2026-04-25T09:30:00",
        "location": "Conference Room A",
        "attendees": ["alice@example.com", "bob@example.com"],
    },
    2: {
        "id": 2,
        "title": "Lunch with Client",
        "description": "Discuss new partnership opportunities",
        "start_time": "2026-04-25T12:00:00",
        "end_time": "2026-04-25T13:30:00",
        "location": "Downtown Bistro",
        "attendees": ["client@company.com"],
    },
    3: {
        "id": 3,
        "title": "Product Demo",
        "description": "Quarterly product showcase",
        "start_time": "2026-04-26T15:00:00",
        "end_time": "2026-04-26T16:00:00",
        "location": "Virtual - Zoom",
        "attendees": ["team@example.com"],
    },
}
_event_counter = 4


# EMAIL TOOLS


@mcp.tool()
def send_email(to: str, subject: str, body: str, from_email: str = "user@example.com") -> str:
    """
    Send an email.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body content
        from_email: Sender email address (defaults to user@example.com)
    """
    global _email_counter

    email = {
        "id": _email_counter,
        "from": from_email,
        "to": to,
        "subject": subject,
        "body": body,
        "timestamp": datetime.now().isoformat(),
        "read": False,  # Recipients would see this as unread
    }

    _emails[_email_counter] = email
    _email_counter += 1

    return json.dumps({"status": "sent", "email": email}, indent=2)


@mcp.tool()
def view_emails(sender: str = "", subject_filter: str = "", unread_only: bool = False, limit: int = 10) -> str:
    """
    View emails with optional filters.

    Args:
        sender: Filter by sender email address (case-insensitive, partial match)
        subject_filter: Filter by subject line (case-insensitive, partial match)
        unread_only: Show only unread emails
        limit: Maximum number of emails to return (default 10)
    """
    emails = list(_emails.values())

    # Apply filters
    if sender:
        emails = [e for e in emails if sender.lower() in e["from"].lower()]

    if subject_filter:
        emails = [e for e in emails if subject_filter.lower() in e["subject"].lower()]

    if unread_only:
        emails = [e for e in emails if not e["read"]]

    # Sort by timestamp (newest first)
    emails.sort(key=lambda x: x["timestamp"], reverse=True)

    # Apply limit
    emails = emails[:limit]

    if not emails:
        return "No emails found matching the criteria."

    return json.dumps(emails, indent=2)


# CALENDAR TOOLS


@mcp.tool()
def create_calendar_event(
    title: str, start_time: str, end_time: str, description: str = "", location: str = "", attendees: str = ""
) -> str:
    """
    Create a calendar event.

    Args:
        title: Event title
        start_time: Start time in ISO format (e.g., "2026-04-25T10:00:00")
        end_time: End time in ISO format (e.g., "2026-04-25T11:00:00")
        description: Event description (optional)
        location: Event location (optional)
        attendees: Comma-separated list of attendee emails (optional)
    """
    global _event_counter

    # Parse attendees
    attendee_list = [a.strip() for a in attendees.split(",")] if attendees else []

    event = {
        "id": _event_counter,
        "title": title,
        "description": description,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "attendees": attendee_list,
    }

    _calendar_events[_event_counter] = event
    _event_counter += 1

    return json.dumps({"status": "created", "event": event}, indent=2)


@mcp.tool()
def view_calendar_events(
    start_date: str = "", end_date: str = "", title_filter: str = "", location_filter: str = ""
) -> str:
    """
    View calendar events with optional filters.

    Args:
        start_date: Show events after this date (ISO format, e.g., "2026-04-25")
        end_date: Show events before this date (ISO format, e.g., "2026-04-30")
        title_filter: Filter by event title (case-insensitive, partial match)
        location_filter: Filter by location (case-insensitive, partial match)
    """
    events = list(_calendar_events.values())

    # Apply filters
    if start_date:
        events = [e for e in events if e["start_time"] >= start_date]

    if end_date:
        events = [e for e in events if e["start_time"] <= end_date]

    if title_filter:
        events = [e for e in events if title_filter.lower() in e["title"].lower()]

    if location_filter:
        events = [e for e in events if location_filter.lower() in e["location"].lower()]

    # Sort by start time
    events.sort(key=lambda x: x["start_time"])

    if not events:
        return "No calendar events found matching the criteria."

    return json.dumps(events, indent=2)


@mcp.tool()
def propose_create_vacation_days(
    title: str,
    start_date: str,
    end_date: str,
    description: str = "",
    half_day: bool = False,
    half_day_period: str = "",
) -> str:
    """
    Propose vacation days for the user to review and confirm.
    Does NOT create the entry — just shows an action card.

    Args:
        title: Title for the vacation entry (e.g. "Summer Vacation")
        start_date: First day of vacation in ISO format (e.g. "2026-05-05")
        end_date: Last day of vacation in ISO format (e.g. "2026-05-09")
        description: Optional reason or notes
        half_day: Whether this is a half-day request
        half_day_period: If half_day is True, specify "morning" or "afternoon"
    """
    return json.dumps(
        {
            "type": "action_card",
            "action": "create_vacation_days",
            "params": {
                "title": title,
                "start_date": start_date,
                "end_date": end_date,
                "description": description,
                "half_day": half_day,
                "half_day_period": half_day_period,
            },
        }
    )


@mcp.tool()
def propose_create_homeoffice(
    date: str,
    recurring: bool = False,
    recurrence_pattern: str = "",
    description: str = "",
) -> str:
    """
    Propose a home office day for the user to review and confirm.
    Does NOT create the entry — just shows an action card.

    Args:
        date: The home office date in ISO format (e.g. "2026-05-05")
        recurring: Whether this should repeat weekly
        recurrence_pattern: If recurring, the pattern (e.g. "every_monday", "every_wednesday")
        description: Optional notes (e.g. "Expecting a delivery")
    """
    return json.dumps(
        {
            "type": "action_card",
            "action": "create_homeoffice",
            "params": {
                "date": date,
                "recurring": recurring,
                "recurrence_pattern": recurrence_pattern,
                "description": description,
            },
        }
    )


@mcp.tool()
def propose_create_sick_leave(
    start_date: str,
    end_date: str,
    has_doctors_note: bool = False,
    doctors_note_date: str = "",
    description: str = "",
) -> str:
    """
    Propose a sick leave entry for the user to review and confirm.
    Does NOT create the entry — just shows an action card.

    Args:
        start_date: First day of sick leave in ISO format (e.g. "2026-05-05")
        end_date: Last day of sick leave in ISO format (e.g. "2026-05-07")
        has_doctors_note: Whether a doctor's note has been provided
        doctors_note_date: Date on the doctor's note, if available
        description: Optional notes
    """
    return json.dumps(
        {
            "type": "action_card",
            "action": "create_sick_leave",
            "params": {
                "start_date": start_date,
                "end_date": end_date,
                "has_doctors_note": has_doctors_note,
                "doctors_note_date": doctors_note_date,
                "description": description,
            },
        }
    )


@mcp.tool()
def propose_create_scrum_story(
    name: str,
    description: str = "",
    acceptance_criteria: str = "",
    story_points: int = 3,
) -> str:
    """
    Propose a scrum story for the user to review and confirm.
    Does NOT create the entry — just shows an action card.
    Args:
        name: Title of the scrum story
        description: Detailed description of the story
        acceptance_criteria: Conditions that must be met for the story to be considered done
        story_points: Estimated effort/complexity (e.g. 1, 2, 3, 5, 8, 13)
    """
    return json.dumps(
        {
            "type": "suggest-ai-app",
            "params": {
                "appName": "Create Scrum Story",
                "appId": "FSCCONTROLTEST@1.1001:AIApplicationTestScrumStoryCreate",
                "appParams": {
                    "name": name,
                    "description": description,
                    "acceptanceCriteria": acceptance_criteria,
                    "storyPoints": story_points,
                },
            },
        }
    )


if __name__ == "__main__":
    # mcp.run()
    mcp.run(
        transport="http",
        port=8001,
        host="0.0.0.0",
        stateless_http=True,
        json_response=True,
    )
