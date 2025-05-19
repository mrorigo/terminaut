        # At this point, self.messages is correctly formatted and truncated.
        # Assert that the first message is still the system message
        assert self.messages[0].get("role") == "system", "After truncation, the first message in self.messages must still have the role 'system'."

        # It starts with a system prompt and respects HISTORY_LIMIT.
        api_call_messages = self.messages