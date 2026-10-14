## Popup Reviewer Configuration

- **interval_minutes** (integer, default `1`): How many minutes between each automatic card popup. Must be 1 or greater.

- **enabled** (boolean, default `true`): Set to `false` to disable the automatic popup timer without uninstalling the addon.

- **cards_per_session** (integer, default `1`): How many cards to review each time the popup fires. Cards are shown one by one.

- **mode** (string, default `"full"`): `"full"` opens a large window that takes focus. `"compact"` shows a small always-on-top popup in the bottom-right corner that doesn't steal focus (click it to use keyboard shortcuts). Drag its header to move it; drag the bottom-right grip to resize.

- **compact_autofit** (boolean, default `true`): In compact mode, fit the card to the popup instead of scrolling: zoom out to fit the width, grow the popup upward (up to 70% of the screen) to fit the height, and only then zoom out further (down to 70%) before scrolling. The size you set by dragging is the minimum.

- **compact_geometry** (list or `null`, default `null`): Remembered `[x, y, width, height]` of the compact popup. Set to `null` to reset it to the bottom-right corner.
