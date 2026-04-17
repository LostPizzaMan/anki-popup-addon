# Popup Reviewer

An Anki addon that automatically pops up a card for review at a set interval, so you can study without manually opening Anki's reviewer.

## How it works

A background timer fires at a set interval. When it does, a popup appears over your current window with the next due card. Grade it, and the popup closes. The timer then resets and counts down from the full interval again.

If you're already in Anki's built-in reviewer when the timer fires, the popup is skipped.

## Installation

1. Download or clone this repository
2. Copy the `anki-popup-addon` folder into your Anki addons directory:
   ```
   %APPDATA%\Anki2\addons21\
   ```
3. Restart Anki
4. The addon will appear under **Tools > Popup Reviewer**

## Usage

### Reviewing a card
- The card front is shown first
- Press **Space** or **Enter** to reveal the answer
- Grade with keyboard shortcuts or buttons:

| Key | Grade |
|-----|-------|
| `1` | Again |
| `2` | Hard |
| `3` | Good |
| `4` | Easy |

### Menu options (Tools > Popup Reviewer)

- **Enabled**: pause or resume the addon without uninstalling
- **Delay**: interval between popups (6 seconds, 1, 5, 10, 15, or 30 minutes)
- **Cards per session**: how many cards to review each time the popup fires (1, 2, 3, 5, or 10). Cards are shown one by one with a progress counter.

## Configuration

Settings can also be edited via **Tools > Add-ons > Popup Reviewer > Config**:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | boolean | `true` | Enable or disable the addon |
| `interval_minutes` | number | `1` | Minutes between popups (supports decimals) |
| `cards_per_session` | integer | `1` | Number of cards per popup session |
