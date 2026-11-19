"""Zengo 禅語: a DeepL-style popup translator for Japanese learners."""

# Bump on every release (see CHANGELOG.md). A newly started copy with a different version
# replaces the one already running, so an update takes effect without hunting in the tray.
__version__ = "1.1.0"

# Bump when scripts/build_dict.py changes the layout of data/zengo.db. update.bat and
# setup.bat rebuild the dictionary when the installed one is older than this.
DICT_SCHEMA = 1
