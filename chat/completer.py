import os
import json

from rich.console import Console
from prompt_toolkit.completion import Completer, Completion


class ChatCompleter(Completer):
    """
    Custom autocomplete that loads prompts from prompts.json.
    It matches against the FULL text the user has typed so far,
    so multi-word phrases like "Write a function" work properly.
    Prompts are organized by category in the JSON file for easy editing.
    """

    def __init__(self):
        self.items = []
        self._load_prompts()

    def _load_prompts(self):
        """Loads all prompt entries from prompts.json into a flat list."""
        # prompts.json lives in the project root (one level up from chat/)
        prompts_path = os.path.join(os.path.dirname(__file__), "..", "prompts.json")
        try:
            with open(prompts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for category in data.values():
                for entry in category:
                    self.items.append((entry["text"], entry["desc"]))
        except FileNotFoundError:
            Console().print("[yellow]Warning: prompts.json not found, autocomplete disabled.[/yellow]")
        except (json.JSONDecodeError, KeyError) as e:
            Console().print(f"[yellow]Warning: prompts.json is invalid ({e}), autocomplete disabled.[/yellow]")

    def get_completions(self, document, complete_event):
        text = document.text
        text_lower = text.lower()

        for item_text, description in self.items:
            if item_text.lower().startswith(text_lower) and text_lower:
                yield Completion(
                    text=item_text,
                    start_position=-len(text),
                    display=item_text.strip(),
                    display_meta=description,
                )
