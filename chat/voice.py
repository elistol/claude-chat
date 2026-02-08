import re

try:
    import win32com.client
    HAS_SAPI = True
except ImportError:
    HAS_SAPI = False

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

from rich.table import Table


class VoiceMixin:
    """
    Mixin that adds voice input/output to ClaudeChat.
    Uses Windows SAPI (win32com) for TTS — reliable, no locking bugs.
    Uses SpeechRecognition + Google for STT.
    Gracefully disables itself if libraries are missing (non-Windows).
    """

    def _init_voice(self):
        """Sets up SAPI voice engine, recognizer, and microphone."""
        self.voice_mode = False
        self.voice_available = False

        if not HAS_SAPI or not HAS_SR:
            return

        try:
            self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
            self.sapi_voices = self.speaker.GetVoices()
            self.current_voice_index = 0
            self.voice_rate = 2  # SAPI rate: -10 (slow) to 10 (fast), 2 = slightly faster than default
            self.speaker.Rate = self.voice_rate
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            self.voice_available = True
        except Exception:
            # SAPI not available (e.g. Wine, server Windows, or COM error)
            pass

    def _voice_name(self, index):
        """Returns a clean voice name like 'David Desktop'."""
        desc = self.sapi_voices.Item(index).GetDescription()
        return desc.split(" - ")[0].replace("Microsoft ", "")

    def do_voice(self):
        """One-shot voice: listens, sends to Claude, speaks the response."""
        if not self.voice_available:
            self._print_error("Voice not available", "Requires Windows with pywin32 and SpeechRecognition installed.")
            return

        self.console.print(f"  {self._c('Voice (' + self._voice_name(self.current_voice_index) + ')', 'accent')}")
        user_msg = self.listen()
        if user_msg:
            self.voice_mode = True
            self.send_message(user_msg)

    def pick_voice(self):
        """Lets the user pick a TTS voice and adjust speed."""
        if not self.voice_available:
            self._print_error("Voice not available", "Requires Windows with pywin32 and SpeechRecognition installed.")
            return

        p = self.theme["primary"]
        table = Table(title="Pick a Voice", show_header=True, header_style=f"bold {p}")
        table.add_column("#", style="bold", width=3)
        table.add_column("Voice", style="bold")
        table.add_column("", style="dim")

        for i in range(self.sapi_voices.Count):
            desc = self.sapi_voices.Item(i).GetDescription()
            name = desc.split(" - ")[0].replace("Microsoft ", "")
            lang = desc.split(" - ")[1] if " - " in desc else ""
            marker = " (current)" if i == self.current_voice_index else ""
            table.add_row(str(i + 1), name + marker, lang)

        self.console.print()
        self.console.print(table)

        while True:
            choice = self._get_input(f"Enter 1-{self.sapi_voices.Count} > ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < self.sapi_voices.Count:
                    self.current_voice_index = index
                    self.speaker.Voice = self.sapi_voices.Item(index)
                    self.console.print(f"  {self._b('-> Voice set to: ' + self._voice_name(index), 'success')}")
                    break
                else:
                    self.console.print(f"  [{self.theme['error']}]Invalid choice.[/{self.theme['error']}]")
            except ValueError:
                self.console.print(f"  [{self.theme['error']}]Please enter a number.[/{self.theme['error']}]")

        # Speed setting
        speed_labels = {-2: "very slow", 0: "default", 2: "normal", 4: "fast", 6: "very fast"}
        current_label = speed_labels.get(self.voice_rate, str(self.voice_rate))
        self.console.print(f"\n  [dim]Current speed: {self.voice_rate} ({current_label})[/dim]")
        speed = self._get_input("Speed (-5=slow, 0=default, 2=normal, 5=fast, or Enter to keep) > ").strip()
        if speed:
            try:
                rate = int(speed)
                rate = max(-10, min(10, rate))
                self.voice_rate = rate
                self.speaker.Rate = rate
                self.console.print(f"  {self._b('-> Speed set to: ' + str(rate), 'success')}")
            except ValueError:
                self.console.print(f"  [{self.theme['error']}]Invalid speed, keeping current.[/{self.theme['error']}]")

    def listen(self):
        """Listens to the microphone and returns the transcribed text."""
        self.console.print(f"  {self._c('Listening... (speak now)', 'accent')}", end="")
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=30)
            self.console.print(f"  [dim]Processing...[/dim]")
            text = self.recognizer.recognize_google(audio)
            self.console.print(f"  {self._c('You said:', 'muted')} {self._b(text)}")
            return text
        except sr.WaitTimeoutError:
            self.console.print(f"\n  [{self.theme['warning']}]No speech detected. Try again or type your message.[/{self.theme['warning']}]")
            return None
        except sr.UnknownValueError:
            self.console.print(f"\n  [{self.theme['warning']}]Could not understand. Try again or type your message.[/{self.theme['warning']}]")
            return None
        except sr.RequestError as e:
            self._print_error("Speech service error", "Google speech recognition is unavailable. Check your internet connection.")
            return None

    def speak(self, text):
        """Speaks the given text aloud using Windows SAPI."""
        if not self.voice_available:
            return
        clean = re.sub(r'[#*`_~\[\]\(\)]', '', text)
        clean = re.sub(r'\n+', '. ', clean)
        self.speaker.Voice = self.sapi_voices.Item(self.current_voice_index)
        self.speaker.Rate = self.voice_rate
        self.speaker.Speak(clean)
