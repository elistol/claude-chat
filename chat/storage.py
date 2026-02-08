import os
import json
from datetime import datetime

from rich.table import Table

from chat.themes import THEMES


class StorageMixin:
    """
    Mixin that handles all persistence for ClaudeChat.
    Config preferences, conversation save/load, markdown export.
    Expects self.console, self.conversation, self.system_prompt,
    self.theme_key, self.theme, self.total_input_tokens, self.total_output_tokens,
    self._b(), self._get_input(), self._update_input_style()
    """

    # --- CONFIG PERSISTENCE ---

    def _load_config(self):
        """Loads saved preferences from config.json if it exists."""
        try:
            with open(self.config_path, "r") as f:
                cfg = json.load(f)
            model_key = cfg.get("model", "")
            if model_key in self.models:
                self.model_name, self.model_id = self.models[model_key]
            brain_key = cfg.get("brain", "")
            if brain_key in self.brain_modes:
                self.brain_name, self.max_tokens = self.brain_modes[brain_key]
            theme_key = cfg.get("theme", "")
            if theme_key in THEMES:
                self.theme_key = theme_key
                self.theme = THEMES[theme_key]
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # first launch — use defaults

    def _save_config(self):
        """Saves current preferences to config.json."""
        model_key = next((k for k, v in self.models.items() if v[0] == self.model_name), "2")
        brain_key = next((k for k, v in self.brain_modes.items() if v[0] == self.brain_name), "3")
        cfg = {"model": model_key, "brain": brain_key, "theme": self.theme_key}
        try:
            with open(self.config_path, "w") as f:
                json.dump(cfg, f)
        except OSError:
            pass  # non-critical — preferences just won't persist this time

    # --- CONVERSATION SAVE/LOAD ---

    def save_conversation(self):
        """Saves the current conversation to a JSON file."""
        if not self.conversation:
            self._print_warning("Nothing to save — conversation is empty.")
            return

        os.makedirs(self.save_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_{timestamp}.json"
        filepath = os.path.join(self.save_dir, filename)

        save_data = {
            "timestamp": timestamp,
            "model": self.model_name,
            "system_prompt": self.system_prompt,
            "theme": self.theme_key,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "last_input_tokens": self.last_input_tokens,
            "conversation": self.conversation,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            self.console.print(f"  {self._b('-> Saved to: ' + filename, 'success')}")
        except PermissionError:
            self._print_error("Can't save conversation", "Permission denied — check folder permissions for saved_chats/.")
        except OSError as e:
            self._print_error("Can't save conversation", f"Disk may be full or path invalid. Details: {e}")

    def load_conversation(self):
        """Shows saved conversations and lets the user pick one to load."""
        if not os.path.exists(self.save_dir):
            self._print_warning("No saved conversations found.")
            return

        files = sorted(
            [f for f in os.listdir(self.save_dir) if f.endswith(".json")],
            reverse=True,
        )

        if not files:
            self._print_warning("No saved conversations found.")
            return

        table = Table(title="Saved Conversations", show_header=True, header_style=f"bold {self.theme['success']}")
        table.add_column("#", style="bold", width=3)
        table.add_column("File", style="bold")
        table.add_column("Model", style="dim")
        table.add_column("Messages", style="dim")

        for i, filename in enumerate(files, 1):
            filepath = os.path.join(self.save_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                msg_count = len(data.get("conversation", [])) // 2
                model = data.get("model", "Unknown")
                table.add_row(str(i), filename, model, str(msg_count))
            except Exception:
                table.add_row(str(i), filename + " [red](corrupted)[/red]", "?", "?")

        self.console.print()
        self.console.print(table)

        choice = self._get_input("Enter number (or empty to cancel) > ").strip()

        if not choice:
            self.console.print("  [dim]Load cancelled.[/dim]")
            return

        try:
            index = int(choice) - 1
            if 0 <= index < len(files):
                filepath = os.path.join(self.save_dir, files[index])
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._print_error(f"Can't load {files[index]}", "This save file is corrupted or unreadable.")
                    return

                self.conversation = data.get("conversation", [])
                self.system_prompt = data.get("system_prompt", "")
                self.total_input_tokens = data.get("total_input_tokens", 0)
                self.total_output_tokens = data.get("total_output_tokens", 0)
                self.total_cost = data.get("total_cost", 0.0)
                self.last_input_tokens = data.get("last_input_tokens", 0)

                # Restore model if saved
                saved_model = data.get("model", "")
                for key, (name, model_id) in self.models.items():
                    if name == saved_model:
                        self.model_name = name
                        self.model_id = model_id
                        break

                # Restore theme if saved
                saved_theme = data.get("theme", "")
                if saved_theme in THEMES:
                    self.theme_key = saved_theme
                    self.theme = THEMES[saved_theme]
                    self._update_input_style()

                msg_count = len(self.conversation) // 2
                self.console.print(
                    f"  {self._b('-> Loaded ' + files[index], 'success')} "
                    f"[dim]({msg_count} exchanges restored)[/dim]"
                )
            else:
                self._print_error("Invalid number", f"Enter a number between 1 and {len(files)}.")
        except ValueError:
            self._print_error("Invalid input", "Please enter a number.")

    # --- MARKDOWN EXPORT ---

    def export_conversation(self):
        """Exports the current conversation as a readable Markdown file."""
        if not self.conversation:
            self._print_warning("Nothing to export — conversation is empty.")
            return

        os.makedirs(self.save_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_{timestamp}.md"
        filepath = os.path.join(self.save_dir, filename)

        lines = [
            f"# Claude Chat Export",
            f"",
            f"**Model:** {self.model_name}  ",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
            f"**Messages:** {len(self.conversation) // 2} exchanges  ",
            f"**Cost:** ${self.total_cost:.4f}",
            f"",
            f"---",
            f"",
        ]

        for msg in self.conversation:
            role = "**You:**" if msg["role"] == "user" else "**Claude:**"
            lines.append(role)
            lines.append("")
            lines.append(msg["content"])
            lines.append("")
            lines.append("---")
            lines.append("")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.console.print(f"  {self._b('-> Exported to: ' + filename, 'success')}")
        except PermissionError:
            self._print_error("Can't export conversation", "Permission denied — check folder permissions for saved_chats/.")
        except OSError as e:
            self._print_error("Can't export conversation", f"Disk may be full or path invalid. Details: {e}")
