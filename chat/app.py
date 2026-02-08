import os
import re
from dotenv import load_dotenv
from anthropic import Anthropic

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.live import Live

from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML

from chat.themes import THEMES
from chat.completer import ChatCompleter
from chat.display import DisplayMixin
from chat.voice import VoiceMixin
from chat.storage import StorageMixin
from chat.web import WebMixin


class ClaudeChat(DisplayMixin, VoiceMixin, StorageMixin, WebMixin):
    """
    The main chatbot class. Inherits display, voice, storage, and web from mixins.
    Features: model switching, brain modes, streaming, system prompts,
    token tracking, save/load conversations, themes, Rich UI, Prompt Toolkit input.
    """

    PRICING = {
        "Opus":   {"input": 15.00, "output": 75.00},
        "Sonnet": {"input": 3.00,  "output": 15.00},
        "Haiku":  {"input": 0.80,  "output": 4.00},
    }

    # --- SETUP ---

    def __init__(self):
        """Runs when we create the chatbot object. Sets everything up."""

        load_dotenv()
        self.console = Console()
        self.project_root = os.path.dirname(os.path.dirname(__file__))

        api_key = os.getenv('api_key')
        if not api_key:
            self.console.print(Panel(
                "[bold red]API key not found[/bold red]\n\n"
                "[dim]1. Create a [bold].env[/bold] file in the project root\n"
                "2. Add this line:[/dim]  [bold]api_key=sk-ant-your-key-here[/bold]\n"
                "[dim]3. Get a key at:[/dim]  [bold cyan]https://console.anthropic.com/[/bold cyan]",
                title="[red]Setup Required[/red]",
                border_style="red",
                padding=(1, 2),
            ))
            exit(1)
        self.client = Anthropic(api_key=api_key)
        self.conversation = []
        self.system_prompt = ""
        self.base_instructions = (
            "Never start your response with a title or heading. Jump straight into the answer.\n\n"
            "IMPORTANT: You are running inside 'Claude Chat', a feature-rich terminal chatbot. "
            "You are NOT running in a browser or API playground. "
            "When the user asks about your capabilities, how to do something, or asks for help, "
            "you MUST answer based on the actual features of this app listed below. "
            "Do NOT give generic answers about what Claude can or can't do — "
            "answer based on what THIS app supports:\n\n"
            "FEATURES THE USER CAN USE (type these as their message):\n"
            "- switch_model → change between Opus, Sonnet, and Haiku models\n"
            "- brain → change response depth (128 to 4096 tokens)\n"
            "- persona → pick a personality preset or write a custom system prompt\n"
            "- theme → switch between 6 color themes (Ocean, Sunset, Forest, Neon, Monochrome, Dracula)\n"
            "- voice → speak a message into the mic and hear the reply read aloud (Windows only)\n"
            "- voice_settings → pick a TTS voice and adjust speed\n"
            "- search → search the web via DuckDuckGo, results are fed to you as context\n"
            "- save → save the conversation to a JSON file\n"
            "- load → load a previously saved conversation\n"
            "- export → export the chat as a readable Markdown file\n"
            "- clear → clear the conversation history and start fresh\n"
            "- help → show the animated help panel with all commands\n"
            "- @file <path> → attach a local file (e.g. '@file chat/app.py explain this'). "
            "The file contents are sent to you so you can read, review, explain, or debug code\n"
            '- """ → enter multi-line input mode for pasting code blocks or long text\n'
            "- quit / exit / q → exit with a session summary showing tokens and cost\n\n"
            "The user's preferences (model, brain mode, theme) are saved automatically between sessions. "
            "When asked about files, sharing code, uploading, etc. — always mention the @file command. "
            "When asked about searching — always mention the search command or trigger phrases."
        )
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.last_input_tokens = 0
        self.context_limit = 180_000  # safe ceiling (models support 200K)

        # Current theme - default to Ocean
        self.theme = THEMES["ocean"]
        self.theme_key = "ocean"

        self.models = {
            "1": ("Opus", "claude-opus-4-20250514"),
            "2": ("Sonnet", "claude-sonnet-4-20250514"),
            "3": ("Haiku", "claude-haiku-4-5-20251001"),
        }
        self.brain_modes = {
            "1": ("Minimal", 128),
            "2": ("Concise", 512),
            "3": ("Standard", 1024),
            "4": ("Detailed", 2048),
            "5": ("Maximum", 4096),
        }

        # Defaults (Sonnet + Standard + Ocean)
        self.model_name, self.model_id = self.models["2"]
        self.brain_name, self.max_tokens = self.brain_modes["3"]

        # Load saved preferences (overrides defaults if config exists)
        self.config_path = os.path.join(self.project_root, "config.json")
        self._load_config()

        # Paths
        self.save_dir = os.path.join(self.project_root, "saved_chats")

        # Voice (from VoiceMixin)
        self._init_voice()

        self.magic_words = {
            "switch_model": self.pick_model,
            "brain": self.pick_brain,
            "persona": self.pick_persona,
            "theme": self.pick_theme,
            "voice": self.do_voice,
            "voice_settings": self.pick_voice,
            "search": self.do_search,
            "clear": self.clear_conversation,
            "save": self.save_conversation,
            "load": self.load_conversation,
            "export": self.export_conversation,
            "help": self.show_help,
        }

        # --- PROMPT TOOLKIT SETUP ---
        self.history = InMemoryHistory()
        self.completer = ChatCompleter()
        self.auto_suggest = AutoSuggestFromHistory()
        self._update_input_style()

    def _update_input_style(self):
        """Updates the Prompt Toolkit style to match the current theme."""
        self.input_style = PTStyle.from_dict({
            "prompt": self.theme["user_prompt"],
            "bottom-toolbar": f"bg:{self.theme['toolbar_bg']} {self.theme['toolbar_fg']}",
            "bottom-toolbar.text": f"bg:{self.theme['toolbar_bg']} {self.theme['toolbar_fg']}",
        })

    # --- THEME HELPERS ---

    def _c(self, text, color_key="primary"):
        """Wraps text in the theme's color."""
        color = self.theme[color_key]
        return f"[{color}]{text}[/{color}]"

    def _b(self, text, color_key="primary"):
        """Wraps text in bold + theme color."""
        color = self.theme[color_key]
        return f"[bold {color}]{text}[/bold {color}]"

    # --- STATUS & INPUT ---

    def _print_status(self):
        """Prints current settings in a neat colored line."""
        brain_colors = {128: "green", 512: "cyan", 1024: "blue", 2048: "magenta", 4096: "red"}
        brain_color = brain_colors.get(self.max_tokens, "yellow")
        persona_label = (
            f"[italic]{self.system_prompt[:30]}...[/italic]"
            if len(self.system_prompt) > 30
            else (f"[italic]{self.system_prompt}[/italic]" if self.system_prompt else "[dim]None[/dim]")
        )
        p = self.theme["primary"]
        self.console.print(
            f"  [dim]Model:[/dim] [bold {p}]{self.model_name}[/bold {p}]"
            f"  [dim]|[/dim]  "
            f"[dim]Brain:[/dim] [{brain_color}]{self.brain_name}[/{brain_color}] [dim]({self.max_tokens} tokens)[/dim]"
            f"  [dim]|[/dim]  "
            f"[dim]Persona:[/dim] {persona_label}"
            f"  [dim]|[/dim]  "
            f"[dim]Theme:[/dim] [{p}]{self.theme['name']}[/{p}]"
        )

    def _print_token_usage(self, input_tokens, output_tokens):
        """Prints token usage and estimated cost as a neat table."""
        prices = self.PRICING.get(self.model_name, {"input": 3.00, "output": 15.00})

        msg_cost_in = (input_tokens / 1_000_000) * prices["input"]
        msg_cost_out = (output_tokens / 1_000_000) * prices["output"]
        msg_cost_total = msg_cost_in + msg_cost_out

        session_cost_total = self.total_cost

        s = self.theme["secondary"]
        table = Table(
            show_header=True,
            header_style=f"bold {self.theme['warning']}",
            border_style="dim",
            title=f"Usage ({self.model_name})",
            title_style="dim",
            padding=(0, 1),
        )
        table.add_column("", style="dim", width=12)
        table.add_column("Input", style=self.theme["primary"], justify="right")
        table.add_column("Output", style=s, justify="right")
        table.add_column("Cost", style=self.theme["warning"], justify="right")

        table.add_row(
            "This msg",
            f"{input_tokens:,}",
            f"{output_tokens:,}",
            f"${msg_cost_total:.4f}",
        )
        table.add_row(
            "Session",
            f"{self.total_input_tokens:,}",
            f"{self.total_output_tokens:,}",
            f"[bold]${session_cost_total:.4f}[/bold]",
        )

        self.console.print(table)

    def _get_toolbar(self):
        """Returns the bottom toolbar text."""
        msgs = len(self.conversation) // 2
        return HTML(
            f"  <b>Model:</b> {self.model_name}  <b>|</b>  "
            f"<b>Brain:</b> {self.brain_name}  <b>|</b>  "
            f"<b>Theme:</b> {self.theme['name']}  <b>|</b>  "
            f"<b>Messages:</b> {msgs}  <b>|</b>  "
            f"<i>Type </i><b>help</b><i> for commands</i>"
        )

    def _get_input(self, prompt_text="You > "):
        """Gets input using Prompt Toolkit with autocomplete, history, and toolbar."""
        return prompt(
            [("class:prompt", prompt_text)],
            history=self.history,
            completer=self.completer,
            auto_suggest=self.auto_suggest,
            bottom_toolbar=self._get_toolbar,
            style=self.input_style,
            complete_while_typing=True,
        )

    # --- SETTINGS PICKERS ---

    def pick_model(self):
        """Asks the user to choose a model with a pretty table."""
        p = self.theme["primary"]
        table = Table(title="Pick a Model", show_header=True, header_style=f"bold {p}")
        table.add_column("#", style="bold", width=3)
        table.add_column("Model", style="bold")
        table.add_column("Description", style="dim")

        table.add_row("1", "Opus", "Most powerful, slowest")
        table.add_row("2", "Sonnet", "Balanced speed & quality")
        table.add_row("3", "Haiku", "Fastest, cheapest")

        self.console.print()
        self.console.print(table)

        while True:
            choice = self._get_input("Enter 1-3 (or empty to cancel) > ").strip().lower()
            if not choice:
                self.console.print("  [dim]Cancelled, keeping current model.[/dim]")
                return
            if choice in self.models:
                self.model_name, self.model_id = self.models[choice]
                self.console.print(f"  {self._b('-> Model set to: ' + self.model_name, 'success')}")
                self._save_config()
                break
            else:
                self.console.print(f"  [{self.theme['error']}]Invalid choice. Enter 1, 2, or 3.[/{self.theme['error']}]")

    def pick_brain(self):
        """Asks the user to choose response depth with a pretty table."""
        s = self.theme["secondary"]
        table = Table(title="Pick Response Depth", show_header=True, header_style=f"bold {s}")
        table.add_column("#", style="bold", width=3)
        table.add_column("Mode", style="bold")
        table.add_column("Tokens", justify="right", style="dim")
        table.add_column("Best for", style="dim")

        table.add_row("1", "Minimal",  "128",  "One-liners, yes/no, definitions")
        table.add_row("2", "Concise",  "512",  "Short explanations, quick help")
        table.add_row("3", "Standard", "1024", "Normal conversations, Q&A")
        table.add_row("4", "Detailed", "2048", "Thorough explanations, code generation")
        table.add_row("5", "Maximum",  "4096", "Long-form content, full documents")

        self.console.print()
        self.console.print(table)

        while True:
            choice = self._get_input("Enter 1-5 (or empty to cancel) > ").strip().lower()
            if not choice:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if choice in self.brain_modes:
                self.brain_name, self.max_tokens = self.brain_modes[choice]
                self.console.print(f"  {self._b(f'-> Response depth: {self.brain_name} ({self.max_tokens} tokens)', 'success')}")
                self._save_config()
                break
            else:
                self.console.print(f"  [{self.theme['error']}]Invalid choice. Enter 1-5.[/{self.theme['error']}]")

    def pick_theme(self):
        """Lets the user pick a color theme. Changes take effect immediately."""
        p = self.theme["primary"]
        table = Table(title="Pick a Theme", show_header=True, header_style=f"bold {p}")
        table.add_column("#", style="bold", width=3)
        table.add_column("Theme", style="bold")
        table.add_column("Style", style="dim")

        theme_list = list(THEMES.keys())

        for i, key in enumerate(theme_list, 1):
            marker = " (current)" if key == self.theme_key else ""
            table.add_row(str(i), THEMES[key]["name"] + marker, THEMES[key].get("description", ""))

        self.console.print()
        self.console.print(table)

        while True:
            choice = self._get_input(f"Enter 1-{len(theme_list)} (or empty to cancel) > ").strip()
            if not choice:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            try:
                index = int(choice) - 1
                if 0 <= index < len(theme_list):
                    self.theme_key = theme_list[index]
                    self.theme = THEMES[self.theme_key]
                    self._update_input_style()
                    self.console.print(f"  {self._b('-> Theme set to: ' + self.theme['name'], 'success')}")
                    self._save_config()
                    break
                else:
                    self.console.print(f"  [{self.theme['error']}]Invalid choice.[/{self.theme['error']}]")
            except ValueError:
                self.console.print(f"  [{self.theme['error']}]Please enter a number.[/{self.theme['error']}]")

    PERSONA_PRESETS = {
        "1": ("Reset to Default", ""),
        "2": ("Python Tutor", "You are a friendly Python tutor for beginners. Explain concepts simply with examples."),
        "3": ("Senior Developer", "You are a senior software developer doing code reviews. Be thorough, suggest improvements, and catch bugs."),
        "4": ("Concise Mode", "Be very concise. Use bullet points. No fluff. Get straight to the point."),
        "5": ("Creative Writer", "You are a creative writer. Use vivid language, metaphors, and storytelling in your responses."),
        "6": ("Explain Like I'm 5", "Explain everything as if I'm 5 years old. Use simple words, analogies, and fun examples."),
        "7": ("Debug Expert", "You are a debugging expert. Analyze code carefully, find bugs, explain root causes, and suggest fixes step by step."),
        "8": ("Custom", None),
    }

    def pick_persona(self):
        """Lets the user pick a preset persona or write a custom one."""
        s = self.theme["secondary"]
        table = Table(title="Pick a Persona", show_header=True, header_style=f"bold {s}")
        table.add_column("#", style="bold", width=3)
        table.add_column("Persona", style="bold")
        table.add_column("Description", style="dim", max_width=50)

        for key, (name, prompt_text) in self.PERSONA_PRESETS.items():
            desc = prompt_text[:50] + "..." if prompt_text and len(prompt_text) > 50 else (prompt_text or "Standard Claude, no special instructions")
            marker = " (current)" if prompt_text == self.system_prompt else ""
            if name == "Reset to Default" and not self.system_prompt:
                marker = " (current)"
            table.add_row(key, name + marker, desc)

        self.console.print()
        self.console.print(table)

        while True:
            choice = self._get_input(f"Enter 1-{len(self.PERSONA_PRESETS)} (or empty to cancel) > ").strip()
            if not choice:
                self.console.print("  [dim]Cancelled, keeping current persona.[/dim]")
                return
            if choice in self.PERSONA_PRESETS:
                name, prompt_text = self.PERSONA_PRESETS[choice]

                if prompt_text is None:
                    custom = self._get_input("Enter your custom persona > ").strip()
                    if custom:
                        self.system_prompt = custom
                        self.console.print(f"  {self._b('-> Persona set to: ' + custom, 'success')}")
                    else:
                        self.console.print(f"  [dim]Cancelled, keeping current persona.[/dim]")
                else:
                    self.system_prompt = prompt_text
                    if prompt_text:
                        self.console.print(f"  {self._b('-> Persona set to: ' + name, 'success')}")
                    else:
                        self.console.print(f"  {self._b('-> Persona reset to default', 'warning')}")
                break
            else:
                self.console.print(f"  [{self.theme['error']}]Invalid choice. Enter 1-{len(self.PERSONA_PRESETS)}.[/{self.theme['error']}]")

    # --- COMMANDS ---

    def do_search(self):
        """Prompts for a search query, searches the web, and sends results to Claude."""
        query = self._get_input("Search > ").strip()
        if query:
            self.send_with_search(f"search for {query}")

    def clear_conversation(self):
        """Clears the conversation history to start fresh."""
        msg_count = len(self.conversation) // 2
        self.conversation = []
        self.console.print(
            f"  {self._b('-> Conversation cleared!', 'success')} "
            f"[dim]({msg_count} exchanges removed)[/dim]"
        )

    # --- CHAT ENGINE ---

    def _trim_conversation(self):
        """Trims oldest message pairs if approaching the context limit."""
        if self.last_input_tokens < self.context_limit * 0.85:
            return

        trimmed = 0
        target = int(len(self.conversation) * 0.7)
        while len(self.conversation) > target and len(self.conversation) > 2:
            if (len(self.conversation) >= 2
                    and self.conversation[0]["role"] == "user"
                    and self.conversation[1]["role"] == "assistant"):
                self.conversation.pop(0)
                self.conversation.pop(0)
                trimmed += 1
            else:
                break

        if trimmed:
            self._print_warning(f"Memory trimmed: removed {trimmed} oldest exchanges to stay within context limit.")

    def send_message(self, user_msg, api_msg=None):
        """Sends a message to Claude using streaming.
        api_msg: if provided, sent to the API instead of user_msg (e.g. with search context).
                 The clean user_msg is what gets stored in conversation history.
        """
        self._trim_conversation()
        self.conversation.append({"role": "user", "content": user_msg})

        if api_msg:
            messages = self.conversation[:-1] + [{"role": "user", "content": api_msg}]
        else:
            messages = self.conversation

        try:
            api_args = {
                "model": self.model_id,
                "max_tokens": self.max_tokens,
                "messages": messages,
            }
            system = self.base_instructions
            if self.system_prompt:
                system += "\n\n" + self.system_prompt
            api_args["system"] = system

            chunks = []

            with self.client.messages.stream(**api_args) as stream:
                self.console.print(Panel.fit(
                    self._b("Claude"),
                    border_style=self.theme["primary"],
                ))

                with Live(console=self.console, refresh_per_second=15) as live:
                    for text_chunk in stream.text_stream:
                        chunks.append(text_chunk)
                        live.update(Markdown("".join(chunks)))

            full_response = "".join(chunks)

            final_message = stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens

            self.last_input_tokens = input_tokens
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            prices = self.PRICING.get(self.model_name, {"input": 3.00, "output": 15.00})
            self.total_cost += (input_tokens / 1_000_000) * prices["input"]
            self.total_cost += (output_tokens / 1_000_000) * prices["output"]

            self.conversation.append({"role": "assistant", "content": full_response})

            self._print_token_usage(input_tokens, output_tokens)

            if self.voice_mode:
                self.speak(full_response)
                self.voice_mode = False

        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "authentication" in error_str:
                self._print_error("Invalid API key", "Check your .env file — the key may be expired or incorrect.")
            elif "429" in error_str or "rate" in error_str:
                self._print_error("Rate limited", "Too many requests — wait a moment and try again.")
            elif "overloaded" in error_str or "529" in error_str:
                self._print_error("Claude is overloaded", "The API is busy right now — try again in a few seconds.")
            elif "connection" in error_str or "timeout" in error_str:
                self._print_error("Connection failed", "Check your internet connection and try again.")
            else:
                self._print_error("Something went wrong", f"Details: {e}")
            self.conversation.pop()
            self.voice_mode = False

    def _show_session_summary(self):
        """Shows a recap of the session before exiting."""
        msgs = len(self.conversation) // 2

        if msgs == 0:
            self.console.print(Panel("[bold]Goodbye![/bold]", border_style=self.theme["warning"]))
            return

        table = Table(
            show_header=False,
            border_style=self.theme["warning"],
            title="Session Summary",
            title_style=f"bold {self.theme['warning']}",
            padding=(0, 2),
        )
        table.add_column("Label", style="dim")
        table.add_column("Value", style="bold")

        table.add_row("Messages", f"{msgs} exchanges")
        table.add_row("Model", self.model_name)
        table.add_row("Theme", self.theme["name"])
        table.add_row("Tokens used", f"{self.total_input_tokens:,} in + {self.total_output_tokens:,} out")
        table.add_row("Total cost", f"${self.total_cost:.4f}")

        self.console.print()
        self.console.print(table)
        self.console.print(Panel("[bold]Goodbye![/bold]", border_style=self.theme["warning"]))

    # --- FILE CONTEXT ---

    def _extract_file_refs(self, message):
        """Extracts @file paths from a message. Returns (file_paths, clean_message)."""
        file_paths = re.findall(r'@file\s+([\S]+)', message)
        clean = re.sub(r'@file\s+[\S]+\s*', '', message).strip()
        return file_paths, clean

    def _read_files(self, file_paths):
        """Reads files and returns formatted context string. Shows UI feedback."""
        context_parts = []

        for path in file_paths:
            if not os.path.isabs(path):
                full_path = os.path.join(self.project_root, path)
            else:
                full_path = path

            if not os.path.isfile(full_path):
                self._print_error(f"File not found: {path}", "Paths are relative to the project root. Example: @file chat/app.py")
                continue

            size = os.path.getsize(full_path)
            if size > 100_000:
                self._print_error(f"File too large: {path} ({size:,} bytes)", "Max file size is 100KB. Try a smaller file or split it up.")
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                line_count = content.count("\n") + 1
                self.console.print(f"  {self._c('Loaded:', 'accent')} {self._b(path)} [dim]({line_count} lines)[/dim]")
                context_parts.append(f"[File: {path} ({line_count} lines)]\n\n{content}")
            except UnicodeDecodeError:
                self._print_error(f"Can't read {path}", "This looks like a binary file. Only text files are supported.")
            except PermissionError:
                self._print_error(f"Access denied: {path}", "You don't have permission to read this file.")
            except Exception as e:
                self._print_error(f"Could not read {path}", str(e))

        return "\n\n---\n\n".join(context_parts) if context_parts else None

    # --- INPUT DISPATCHER ---

    def handle_input(self, user_msg):
        """Decides what to do with the user's input."""
        stripped = user_msg.strip().lower()

        if stripped in ("quit", "exit", "q"):
            self._show_session_summary()
            return False

        if stripped in self.magic_words:
            self.magic_words[stripped]()
            self._print_status()
            return True

        # Check for @file references
        if "@file " in user_msg:
            file_paths, clean_msg = self._extract_file_refs(user_msg)
            if file_paths:
                file_context = self._read_files(file_paths)
                if file_context:
                    augmented = f"{file_context}\n\n---\n\n{clean_msg or 'Explain this code.'}"
                    self.send_message(clean_msg or user_msg, api_msg=augmented)
                else:
                    if clean_msg:
                        self.send_message(clean_msg)
                    else:
                        self._print_warning("No files loaded and no message to send.")
                self._print_status()
                return True

        # Check if the user wants a web search
        if self._has_search_intent(user_msg):
            self.send_with_search(user_msg)
        else:
            self.send_message(user_msg)
        self._print_status()
        return True

    # --- MAIN LOOP ---

    def run(self):
        """Starts the chatbot and enters the chat loop."""

        try:
            os.system('cls' if os.name == 'nt' else 'clear')
        except Exception:
            pass  # terminal clear failed — not critical

        self._print_banner()
        self.show_help()
        self._print_status()
        self.console.rule(style="dim")

        while True:
            try:
                user_msg = self._get_input("You > ")
                if not user_msg.strip():
                    continue

                # Multi-line mode: type """ to start, """ to finish
                if user_msg.strip() == '"""':
                    self.console.print(f"  [dim]Multi-line mode. Type [bold]\"\"\"[/bold] on its own line to send.[/dim]")
                    lines = []
                    while True:
                        line = self._get_input("... > ")
                        if line.strip() == '"""':
                            break
                        lines.append(line)
                    user_msg = "\n".join(lines)
                    if not user_msg.strip():
                        continue

                keep_going = self.handle_input(user_msg)
                if not keep_going:
                    break
                self.console.rule(style="dim")
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n")
                self._show_session_summary()
                break
