from typing import Any, Dict, List, Optional


class MessageHistory:
    """Manages the list of messages and handles history truncation."""
    def __init__(self, history_limit: int):
        self._messages: List[Dict[str, Any]] = []
        self._history_limit = history_limit

    def add_message(self, message: Dict[str, Any]):
        """Adds a single message to the history."""
        self._messages.append(message)

    def add_messages(self, messages: List[Dict[str, Any]]):
        """Adds multiple messages to the history."""
        self._messages.extend(messages)

    def clear_system_messages(self):
        """Removes all messages with the 'system' role."""
        self._messages = [msg for msg in self._messages if msg.get("role") != "system"]

    def insert_system_message(self, system_prompt_content: str):
        """Inserts a system message at the beginning of the history."""
        # Ensure only one system message is ever at the start
        if self._messages and self._messages[0].get("role") == "system":
             # This should not happen if clear_system_messages is called first,
             # but as a safeguard, update the existing one or replace it.
             # Replacing is safer to guarantee structure.
             self._messages.pop(0)
        self._messages.insert(0, {"role": "system", "content": system_prompt_content})

    def get_truncated_history(self) -> List[Dict[str, Any]]:
        """
        Returns the history messages truncated according to the limit.
        The system message (if present) is always kept.
        If HISTORY_LIMIT > 1, at least one non-system message is kept.
        Prioritizes the first user message and the most recent messages.
        """
        # Ensure HISTORY_LIMIT is at least 2 (1 system + 1 other)
        effective_limit = max(2, self._history_limit)

        if not self._messages:
            return []

        system_msg = None
        other_messages = []
        first_user_msg = None

        # Separate system message and identify the first user message
        for msg in self._messages:
            if msg.get("role") == "system" and system_msg is None:
                 system_msg = msg # Assume the first system message is the main one
            else:
                 other_messages.append(msg)
                 if msg.get("role") == "user" and first_user_msg is None:
                      first_user_msg = msg

        kept_messages = []
        if system_msg:
            kept_messages.append(system_msg)

        num_slots_for_others = effective_limit - len(kept_messages) # At least 1 slot if system_msg is present

        if num_slots_for_others <= 0:
             # If effective_limit is 1 or less and system_msg is present, only keep system.
             # This shouldn't happen with effective_limit >= 2.
             return kept_messages

        messages_to_consider_for_other = []
        if first_user_msg and first_user_msg in other_messages:
             # Add the first user message if it exists in the non-system messages list
             messages_to_consider_for_other.append(first_user_msg)

        # Add recent messages from the 'other_messages' list
        # Exclude the first user message if it was already added to avoid duplication
        recent_other_messages = [
            msg for msg in other_messages
            if msg != first_user_msg
        ]

        # Take the most recent messages from 'recent_other_messages' to fill remaining slots
        num_recent_to_take = num_slots_for_others - len(messages_to_consider_for_other)
        if num_recent_to_take > 0:
            messages_to_consider_for_other.extend(recent_other_messages[-num_recent_to_take:])

        # Combine and sort by original index to maintain chronological order
        # (Need to map back to original _messages list for index)
        original_indices = {id(msg): i for i, msg in enumerate(self._messages)}

        combined_candidates = kept_messages + messages_to_consider_for_other
        # Remove duplicates based on identity (object reference)
        seen_ids = set()
        deduplicated_candidates = []
        for msg in combined_candidates:
            if id(msg) not in seen_ids:
                deduplicated_candidates.append(msg)
                seen_ids.add(id(msg))

        # Sort by their index in the original self._messages list
        deduplicated_candidates.sort(key=lambda msg: original_indices.get(id(msg), -1)) # Use -1 for system if needed, though it's added first

        return deduplicated_candidates

    def get_messages(self) -> List[Dict[str, Any]]:
        """Returns the full current message history."""
        return self._messages

    def get_latest_user_message(self) -> Optional[Dict[str, Any]]:
        """Find and return the most recent user message."""
        for msg in reversed(self._messages):
            if msg.get("role") == "user" and "content" in msg:
                return msg
        return None
