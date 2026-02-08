import re

from ddgs import DDGS

from rich.panel import Panel
from rich.table import Table


# Phrases that trigger a web search (must be specific to avoid false positives)
SEARCH_TRIGGERS = [
    "search for", "search about", "look up", "google",
    "find online", "what's the latest",
    "latest news", "current price", "weather in",
    "search the web", "look online", "web search",
]


class WebMixin:
    """
    Mixin that adds web search to ClaudeChat.
    Detects search intent in messages and fetches results from DuckDuckGo.
    Results are injected as context so Claude can answer with fresh info.
    """

    def _has_search_intent(self, message):
        """Checks if the user's message wants a web search."""
        msg_lower = message.lower()
        return any(trigger in msg_lower for trigger in SEARCH_TRIGGERS)

    def _extract_query(self, message):
        """Extracts the search query from the user's message."""
        msg_lower = message.lower()
        for trigger in SEARCH_TRIGGERS:
            if trigger in msg_lower:
                # Get everything after the trigger phrase
                idx = msg_lower.index(trigger) + len(trigger)
                query = message[idx:].strip().strip('"').strip("'")
                if query:
                    return query
        # Fallback: use the whole message
        return message

    def web_search(self, query, max_results=5):
        """Searches DuckDuckGo and returns results."""
        self.console.print(f"  {self._c('Searching the web for:', 'accent')} {self._b(query)}")

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                self.console.print(f"  [{self.theme['warning']}]No results found.[/{self.theme['warning']}]")
                return None

            # Show results table
            table = Table(
                title=f"Web Results ({len(results)})",
                show_header=True,
                header_style=f"bold {self.theme['accent']}",
                border_style="dim",
                padding=(0, 1),
            )
            table.add_column("#", style="bold", width=3)
            table.add_column("Title", style="bold", max_width=40)
            table.add_column("Source", style="dim", max_width=25)

            for i, r in enumerate(results, 1):
                title = r.get("title", "No title")
                href = r.get("href", "")
                # Extract domain from URL
                domain = re.sub(r'https?://(www\.)?', '', href).split('/')[0] if href else ""
                table.add_row(str(i), title[:40], domain[:25])

            self.console.print(table)

            # Build context string for Claude
            context_parts = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                context_parts.append(f"Title: {title}\nURL: {href}\nSnippet: {body}")

            return "\n\n---\n\n".join(context_parts)

        except Exception as e:
            self.console.print(f"  [{self.theme['error']}]Search failed: {e}[/{self.theme['error']}]")
            return None

    def send_with_search(self, user_msg):
        """Searches the web, then sends the message to Claude with search context."""
        query = self._extract_query(user_msg)
        results = self.web_search(query)

        if results:
            # Build augmented message for the API only — clean user_msg goes in history
            augmented_msg = (
                f"{user_msg}\n\n"
                f"[Web search results for: {query}]\n\n"
                f"{results}\n\n"
                f"Use the above web search results to help answer my question. "
                f"Cite sources when relevant."
            )
            self.send_message(user_msg, api_msg=augmented_msg)
        else:
            # No results, send normally
            self.send_message(user_msg)
