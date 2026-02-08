# Claude Chat

A feature-rich terminal chatbot powered by Anthropic's Claude API. Built with Python, styled with Rich, and designed for power users who prefer the command line.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude_API-blueviolet)
![Platform](https://img.shields.io/badge/Platform-Windows_%7C_macOS_%7C_Linux-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

<!-- Screenshot: main chat view -->
<!-- ![Claude Chat Banner](screenshots/banner.png) -->

---

## Features

### Chat
- **Streaming responses** -- watch Claude think in real-time with live Markdown rendering
- **Model switching** -- swap between Opus, Sonnet, and Haiku on the fly
- **Brain modes** -- control response depth from 128 to 4,096 tokens
- **Token tracking** -- per-message and session cost estimates with a detailed usage table
- **Conversation save/load** -- persist chats as JSON and resume them later
- **Markdown export** -- export conversations as readable `.md` files for sharing
- **Multi-line input** -- type `"""` to enter multi-line mode for pasting code or writing paragraphs
- **Smart memory** -- automatically trims oldest messages when approaching the context limit so long chats never crash
- **File context (`@file`)** -- reference local files in your message so Claude can review, explain, or debug your code

### Personas
- **7 built-in presets** -- Python Tutor, Senior Developer, Concise Mode, Creative Writer, ELI5, Debug Expert, and a default reset
- **Custom personas** -- write your own system prompt on the fly

### Themes
- **6 color themes** -- Ocean, Sunset, Forest, Neon, Monochrome, Dracula
- **Full UI theming** -- prompt colors, toolbar, panels, and tables all adapt to your theme

### Voice
- **Speech-to-text** -- speak your message using your microphone (Google STT)
- **Text-to-speech** -- hear Claude's response read aloud (Windows SAPI)
- **Voice picker** -- choose from installed system voices and adjust speed

### Web Search
- **DuckDuckGo integration** -- search the web from the chat with trigger phrases like "search for", "look up", or "google"
- **Auto-detection** -- Claude automatically recognizes search intent in your messages
- **Context injection** -- search results are fed to Claude so it can answer with fresh info and cite sources

### Terminal UX
- **Autocomplete** -- 170+ prompt suggestions loaded from a JSON file, triggered with Tab
- **Message history** -- press Up Arrow to recall previous messages
- **Styled toolbar** -- always shows your current model, brain mode, theme, and message count
- **ASCII banner** -- Claude-orange block-character startup art
- **Animated help** -- live RGB rainbow cycling on the help menu

<!-- Screenshot: theme picker -->
<!-- ![Themes](screenshots/themes.png) -->

---

## Project Structure

```
claude-chat/
├── my_claude.py        # Entry point
├── .env                # API key (create this yourself)
├── .gitignore          # Keeps secrets and junk out of git
├── prompts.json        # 170+ autocomplete prompts
├── requirements.txt    # pip dependencies
├── config.json         # Auto-saved user preferences
├── saved_chats/        # Saved conversations (auto-created)
└── chat/               # Main package
    ├── __init__.py     # Exports ClaudeChat
    ├── app.py          # Core chatbot class, UI, chat loop
    ├── themes.py       # 6 color theme definitions
    ├── completer.py    # Tab autocomplete engine
    ├── voice.py        # Voice input/output (SAPI + SpeechRecognition)
    ├── storage.py      # Save/load conversations
    └── web.py          # DuckDuckGo web search
```

---

## Installation

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)
- Windows (for voice features -- chat works on all platforms)

### Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/claude-chat.git
   cd claude-chat
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS / Linux
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   > On macOS/Linux, skip `pywin32` (voice features are Windows-only). Install manually without it:
   > `pip install anthropic python-dotenv rich prompt_toolkit duckduckgo-search SpeechRecognition`

4. **Add your API key**

   Create a `.env` file in the project root:

   ```
   api_key=sk-ant-your-key-here
   ```

5. **Run it**

   ```bash
   python my_claude.py
   ```

---

## Usage

### Quick Start

Launch the app and start chatting. Your last model, brain mode, and theme are remembered automatically:

```
python my_claude.py
```

<!-- Screenshot: startup flow -->
<!-- ![Startup](screenshots/startup.png) -->

### Commands

Type any of these magic words as your message:

| Command          | Action                              |
|------------------|-------------------------------------|
| `switch_model`   | Change AI model (Opus/Sonnet/Haiku) |
| `brain`          | Change response depth (128-4096)    |
| `persona`        | Pick a persona or write a custom one|
| `theme`          | Switch color theme                  |
| `voice`          | Speak one message and hear the reply|
| `voice_settings` | Pick a TTS voice and adjust speed   |
| `search`         | Search the web and ask Claude       |
| `save`           | Save conversation to JSON           |
| `load`           | Load a saved conversation           |
| `export`         | Export conversation as Markdown      |
| `clear`          | Clear conversation history          |
| `help`           | Show all commands                   |
| `@file <path>`   | Send a file to Claude as context    |
| `"""`            | Enter multi-line input mode         |
| `quit` / `q`     | Exit with session summary           |

### Web Search

You can trigger a web search in two ways:

1. Type `search` to get a dedicated search prompt
2. Include a trigger phrase in your message:
   - *"search for latest Python news"*
   - *"look up the weather in Tokyo"*
   - *"google best practices for REST APIs"*

### Voice

Type `voice` to activate a one-shot voice interaction:
1. Speak your message into the microphone
2. Claude responds in text
3. The response is read aloud
4. Returns to text mode automatically

Use `voice_settings` to pick a different voice or adjust speed.

---

## Tech Stack

| Component         | Library                                                       |
|-------------------|---------------------------------------------------------------|
| AI Backend        | [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) |
| Terminal UI       | [Rich](https://github.com/Textualize/rich)                   |
| Input / Autocomplete | [Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) |
| Web Search        | [ddgs](https://github.com/deedy5/duckduckgo_search)          |
| Speech-to-Text    | [SpeechRecognition](https://github.com/Uberi/speech_recognition) |
| Text-to-Speech    | Windows SAPI via [pywin32](https://github.com/mhammond/pywin32) |
| Config            | [python-dotenv](https://github.com/theskumar/python-dotenv)  |

---

## Screenshots

> Add your own screenshots to a `screenshots/` folder and uncomment the image tags above.

| View | Description |
|------|-------------|
| Startup banner | ASCII art with theme colors |
| Chat session | Streaming Markdown response |
| Theme picker | 6 themes to choose from |
| Web search | DuckDuckGo results table |
| Token usage | Per-message and session cost |
| Voice settings | Voice picker with speed control |

---

## License

MIT

---

## Credits

- **Anthropic** -- for the Claude API
- **Will McGugan** -- for the [Rich](https://github.com/Textualize/rich) library
- **DuckDuckGo** -- for the search API
- Built with help from **Claude** itself
