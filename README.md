# Claude Code Buddy

A tiny desktop pet inspired by Claude Code's mascot.

## Files

- `claude_buddy_desktop.pyw` — a borderless, always-on-top pixel mascot that
  floats on your desktop. Drag it, double-click to make it talk, right-click
  for a menu. It randomly cycles through poses (normal, happy, sleepy,
  surprised, wink, working, nap, look-around, jump) and also pops up
  reminders: random health/fun nudges every 5-10 minutes, an hourly time
  chime, three fixed daily greetings (08:30 / 13:30 / 17:00), and a weather
  report (auto-detected location, no API key required) that prioritizes a
  rain/cold/heavy-rain warning when relevant.
- `claude_buddy.py` — a simpler terminal/CLI version of the same pet
  (`status` / `feed` / `play` / `sleep` / `talk` / `reset` subcommands).

## Requirements

- Python 3 with tkinter (bundled with the standard Windows installer)
- Internet access for the weather feature (optional — everything else works
  offline)

## Running

```
pyw claude_buddy_desktop.pyw
```

or on systems without the `py` launcher:

```
pythonw claude_buddy_desktop.pyw
```
