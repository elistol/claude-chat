import time

from rich.panel import Panel
from rich.text import Text
from rich.live import Live


class DisplayMixin:
    """
    Mixin that handles all visual display for ClaudeChat.
    Banner, help panel, RGB animation, error panels.
    Expects self.console, self.theme, self.HELP_COMMANDS from the main class.
    """

    BANNER_LINES = [
        r"   ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗",
        r"  ██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝",
        r"  ██║     ██║     ███████║██║   ██║██║  ██║█████╗  ",
        r"  ██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝  ",
        r"  ╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗",
        r"   ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝",
        r"",
        r"    ██████╗██╗  ██╗ █████╗ ████████╗",
        r"   ██╔════╝██║  ██║██╔══██╗╚══██╔══╝",
        r"   ██║     ███████║███████║   ██║   ",
        r"   ██║     ██╔══██║██╔══██║   ██║   ",
        r"   ╚██████╗██║  ██║██║  ██║   ██║   ",
        r"    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ",
    ]

    HELP_COMMANDS = [
        ("switch_model",   "  - change the AI model"),
        ("brain",          "         - change response depth"),
        ("persona",        "      - set Claude's personality"),
        ("theme",          "        - change color theme"),
        ("voice",          "        - speak one message & hear reply"),
        ("voice_settings", " - pick voice & speed"),
        ("search",         "       - search the web & ask Claude"),
        ("clear",          "        - start fresh conversation"),
        ("save",           "         - save conversation to file"),
        ("load",           "         - load a saved conversation"),
        ("export",         "       - export chat as markdown"),
        ("help",           "         - show this help panel"),
        ("@file <path>",   " - send a file to Claude"),
        ('"""',            "          - multi-line input mode"),
        ("quit/exit/q",    "   - exit the chat"),
    ]

    @staticmethod
    def _hue_to_rgb(h):
        """Converts a hue (0.0-1.0) to an RGB tuple. Full saturation, high brightness."""
        h6 = h * 6.0
        x = int(255 * (1 - abs(h6 % 2 - 1)))
        sector = int(h6) % 6
        return [
            (255, x, 0), (x, 255, 0), (0, 255, x),
            (0, x, 255), (x, 0, 255), (255, 0, x),
        ][sector]

    def _print_banner(self):
        """Prints a large Claude-orange banner on startup."""
        banner = Text()
        for line in self.BANNER_LINES:
            for char in line:
                if char == " ":
                    banner.append(char)
                else:
                    banner.append(char, style="bold #E07A5F")
            banner.append("\n")

        self.console.print(Panel(
            banner,
            subtitle="[dim]Your AI assistant in the terminal[/dim]",
            border_style="#E07A5F",
            padding=(1, 4),
        ))

    def _build_help_panel(self, offset=0.0):
        """Builds the help panel with rainbow colors shifted by offset."""
        help_text = Text()
        help_text.append("Magic words:\n", style="bold")

        for cmd_i, (name, desc) in enumerate(self.HELP_COMMANDS):
            help_text.append("  ")
            for char_i, char in enumerate(name):
                hue = (cmd_i / len(self.HELP_COMMANDS) + char_i * 0.03 + offset) % 1.0
                r, g, b = self._hue_to_rgb(hue)
                help_text.append(char, style=f"bold #{r:02x}{g:02x}{b:02x}")
            help_text.append(f"{desc}\n", style="dim")

        help_text.append("\n")
        help_text.append("Tips: ", style="bold")
        help_text.append("Press ", style="dim")
        for i, c in enumerate("Tab"):
            hue = (0.4 + i * 0.05 + offset) % 1.0
            r, g, b = self._hue_to_rgb(hue)
            help_text.append(c, style=f"bold #{r:02x}{g:02x}{b:02x}")
        help_text.append(" for autocomplete, ", style="dim")
        for i, c in enumerate("Up Arrow"):
            hue = (0.6 + i * 0.04 + offset) % 1.0
            r, g, b = self._hue_to_rgb(hue)
            help_text.append(c, style=f"bold #{r:02x}{g:02x}{b:02x}")
        help_text.append(" for message history", style="dim")

        return Panel(help_text, title="Help", title_align="left", border_style=self.theme["success"])

    def show_help(self):
        """Shows the help panel with live animated rainbow colors."""
        frames = 60  # ~3 seconds at 20fps
        with Live(self._build_help_panel(0), console=self.console, refresh_per_second=20) as live:
            for frame in range(frames):
                offset = frame / 40
                live.update(self._build_help_panel(offset))
                time.sleep(0.05)

    def _print_error(self, message, hint=None):
        """Prints a styled error panel. Optional hint tells the user what to do."""
        body = f"[bold red]{message}[/bold red]"
        if hint:
            body += f"\n[dim]{hint}[/dim]"
        self.console.print(Panel(body, title="[red]Error[/red]", border_style="red", padding=(0, 2)))

    def _print_warning(self, message):
        """Prints a styled warning message."""
        self.console.print(f"  [{self.theme['warning']}]{message}[/{self.theme['warning']}]")
