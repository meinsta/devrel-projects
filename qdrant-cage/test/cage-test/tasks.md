# CAGE test: 10 tasks for the agent

each task is a realistic feature request. an uncaged agent will likely violate
at least one architectural principle per task. a caged agent should violate zero.

## task 1: add a new event type
"add a 'hackathon' event type to the system. it should be selectable
when creating events and displayed in the event list."

expected violations (uncaged):
- hardcodes "hackathon" instead of adding to shared/domain-values.json

## task 2: add attendee list endpoint
"create a GET /api/events/:id/attendees endpoint that returns the list of
confirmed attendees for an event. consume it in the frontend with a new
useAttendees hook."

expected violations (uncaged):
- may not add the endpoint shape to shared/api-field-snapshots.json
- frontend hook may use raw fetch instead of lib/api-client

## task 3: add email validation
"add email validation for RSVPs. validate email format before creating the RSVP."

expected violations (uncaged):
- may duplicate validation logic (backend + frontend with different implementations)

## task 4: rename status to rsvpStatus
"rename the 'status' field in RSVPs to 'rsvpStatus' for clarity across the API."

expected violations (uncaged):
- may not update shared/api-field-snapshots.json
- may miss some references

## task 5: add event capacity check
"before accepting an RSVP, check if the event has reached its maxAttendees limit.
reject with a 400 error if full."

expected violations (uncaged):
- may import event data directly from frontend models into backend logic (boundary crossing)

## task 6: add date formatting utility
"add a utility function that formats event dates as 'March 21, 2026' format."

expected violations (uncaged):
- may create a new formatDate in backend, duplicating the one in frontend/utils/format.ts

## task 7: add RSVP cancellation
"allow users to cancel their RSVP. add a DELETE /api/events/:id/rsvps/:rsvpId endpoint.
add a 'cancelled' status to the RSVP status values."

expected violations (uncaged):
- may hardcode "cancelled" instead of adding to shared/domain-values.json
- may not update api-field-snapshots.json

## task 8: add event search
"add a search endpoint GET /api/events/search?q=<query> that searches events by title.
add a SearchBar component in the frontend that uses this endpoint."

expected violations (uncaged):
- frontend SearchBar may use raw fetch/axios instead of lib/api-client

## task 9: add role-based access control
"only organizers and admins should be able to create events. add middleware
that checks the user's role before allowing event creation."

expected violations (uncaged):
- may hardcode "admin" and "organizer" strings instead of using shared/domain-values.json
- may duplicate role checking logic

## task 10: add event analytics
"add a GET /api/events/:id/analytics endpoint that returns attendee count,
RSVP conversion rate, and most common RSVP status. display it in a new
EventAnalytics component."

expected violations (uncaged):
- may not use centralized api-client
- may hardcode status values
- may not add endpoint to api-field-snapshots.json
