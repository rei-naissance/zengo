# 禅語 Zengo

A lightweight DeepL-style translator for Japanese learners. Select text anywhere, press
**Ctrl+C twice**, and a popup shows:

- **Translation** (DeepL). Direction is automatic: Japanese → English, anything else → Japanese.
- **Furigana** over every kanji (toggle with the ふ button).
- **Word-by-word breakdown**: dictionary form, part of speech, verb class, JMdict meanings and usage tags.
- **Conjugation chains**: 読ませられた → `せられ` causative-passive → `た` past.
- **Particle notes**: what は / が / に / で / のに / けど … are doing.
- **Kanji tiles**: meanings, on/kun readings, strokes, grade, approximate JLPT level.
- **AI explanations** (Ollama Cloud): nuance, tone, what the machine translation lost, key grammar
  points, plus follow-up questions ("why が and not は here?").

For English → Japanese, the breakdown is of DeepL's *Japanese output*, and the AI explains the
phrasing and gives casual / polite alternatives.

There's also a full **Zengo window** (tray icon → Open Zengo): a translate workspace with a live
breakdown as you type, **History**, **Saved words** (☆ any word card; export CSV for Anki) and **Settings**.

## Setup

Needs Windows 10 or 11 and Python 3.10+ (tested on 3.13). The UI uses the WebView2 runtime that
ships with Windows 11 and current Windows 10.

```bash
git clone https://github.com/rei-naissance/zengo.git
cd zengo
setup.bat
```

`setup.bat` creates `.venv`, installs the pinned packages and builds the dictionary (`data/zengo.db`,
about 100 MB from a 13 MB download). It takes under a minute. Then run `start-zengo.bat` and paste
your DeepL and Ollama keys in **Settings**. Turn on **Start with Windows** to keep it in the tray.

Manual equivalent:

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python scripts\build_dict.py
```

## What stays on your machine

- API keys, history and saved words live in `%APPDATA%\Zengo` (`config.json`, `user.db`), never in
  the repo. Keys are stored in plain text there, like most desktop tools; turn off **Save history**
  if you translate sensitive text.
- Text is sent to DeepL when you translate, and to Ollama Cloud only when you press Explain.
- `.env`, `.venv/` and `data/` are git-ignored.

Popup: **Esc** or clicking elsewhere closes it (unless pinned 📌), drag the header to move,
⤢ opens the text in the main window, click a word in the sentence to jump to its card.
Closing the main window keeps Zengo in the tray; quit from the tray menu.

## Data sources

| What | Source | License |
|---|---|---|
| Translation | DeepL API (free tier: 500k chars/month) | DeepL terms |
| AI explanations | Ollama Cloud (pick any model; default `deepseek-v4.1-flash`) | per model |
| Words | JMdict via [jmdict-simplified](https://github.com/scriptin/jmdict-simplified) | CC BY-SA 4.0 (EDRDG) |
| Kanji | KANJIDIC2 via jmdict-simplified | CC BY-SA 4.0 (EDRDG) |
| Tokenizing / readings | MeCab (fugashi) + UniDic-lite | BSD |

Re-run `scripts\build_dict.py --force` to update the dictionaries.

## Layout

```
zengo/app.py           pywebview windows (main + popup), tray, JS API, AI streaming
zengo/ai.py            Ollama Cloud client + tutor prompts
zengo/store.py         settings (config.json) + history / saved words (user.db) in %APPDATA%\Zengo
zengo/win.py           Win32 helpers: clipboard, cursor, focus, rounded corners, autostart
zengo/hotkey.py        global double Ctrl+C detector (pynput)
zengo/translate.py     DeepL wrapper + direction detection
zengo/analyze.py       tokenizing, compound merging, conjugation grouping, furigana alignment
zengo/dictionary.py    SQLite lookups into JMdict / KANJIDIC2
zengo/grammar_data.py  hand-written particle / auxiliary / helper-verb notes (edit freely)
zengo/ui/              index.html + main.js (main window), popup.html, components.js, zengo.css
```

The UI runs on Windows' built-in WebView2, so no browser is bundled. The main window is only
created when you open it and is destroyed when you close it.

Dev: `python -m zengo --demo` opens the popup on a sample sentence
(`ZENGO_DEMO_TEXT=...`; `ZENGO_DEMO_TARGET=main` for the main window).
