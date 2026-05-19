from typing import Any



def _find_last_user_message_index(request_body: dict[str, Any]) -> int | None:
    """Return the index of the last user message in request_body['messages'],
    or None if no user message exists (defensive — pipeline is skipped).
    """
    messages = request_body.get("messages", [])
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            return i
    return None