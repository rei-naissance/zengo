# Changelog

Version numbers live in `zengo/__init__.py` (`__version__`). Bump `DICT_SCHEMA` there too when
`scripts/build_dict.py` changes the dictionary layout, and append a step to `MIGRATIONS` in
`zengo/store.py` when `user.db` changes; never edit a released step.

## 1.1.0

- Long text no longer pushes the translation off-screen: the original collapses to a few lines
  with **Show full text**, and the main window's input box shrinks when you're not typing in it.
- DeepL usage is fetched automatically: a usage meter in Settings, a quota percentage in the
  sidebar, refreshed after translations (popup ones too) and when you return to the window.
  Keys are saved and checked as soon as you paste them; no need to press Test.
- Updating: `update.bat` and **Settings → About & updates** (check, see what changed, update
  and restart), with automatic rollback if the update fails.
- One Zengo at a time, with a hand-off when a different version starts.
- Safer data across versions: atomic config writes, versioned `user.db` with a backup before
  migrating, versioned dictionary built to a temp file and swapped in.
- "Start with Windows" repairs itself if it points at a copy that was moved or deleted.

Upgrading from 1.0: quit 1.0 from its tray icon before starting 1.1 (1.0 can't be asked to
close), then `git pull` and run `setup.bat` once. After that, use `update.bat`.

## 1.0.0

- Initial release.
