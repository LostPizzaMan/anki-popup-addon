import os

from typing import Optional

# os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "8089"

from aqt import gui_hooks, mw
from aqt.qt import QAction, QActionGroup, QMenu, QMessageBox, Qt, QTimer

from .popup import PopupReviewer

_timer: Optional[QTimer] = None

DELAY_OPTIONS = [
    ("6 seconds", 0.1),
    ("1 minute", 1),
    ("5 minutes", 5),
    ("10 minutes", 10),
    ("15 minutes", 15),
    ("30 minutes", 30),
]

CARDS_OPTIONS = [1, 2, 3, 5, 10]


def get_config() -> dict:
    cfg = mw.addonManager.getConfig(__name__)
    if cfg is None:
        cfg = {"interval_minutes": 1, "enabled": True}
    return cfg


def save_config(cfg: dict) -> None:
    mw.addonManager.writeConfig(__name__, cfg)


def stop_timer() -> None:
    global _timer
    if _timer is not None:
        _timer.stop()
        _timer = None


def start_timer() -> None:
    global _timer
    stop_timer()
    cfg = get_config()
    if not cfg.get("enabled", True):
        return
    interval_ms = int(max(0.1, float(cfg.get("interval_minutes", 1))) * 60 * 1000)
    _timer = mw.progress.timer(interval_ms, _on_timer_fire, repeat=False)


def _is_reviewing() -> bool:
    return isinstance(mw.state, str) and mw.state == "review"


def _show_no_cards_due() -> None:
    msg = QMessageBox(mw)
    msg.setWindowTitle("Popup Reviewer")
    msg.setText("No cards are currently due.")
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg.show()


def _on_timer_fire() -> None:
    if mw.col is None:
        start_timer()
        return

    if _is_reviewing():
        start_timer()
        return

    card = mw.col.sched.getCard()

    if card is None:
        _show_no_cards_due()
        start_timer()
        return

    total = int(get_config().get("cards_per_session", 1))
    dlg = PopupReviewer(card, total=total)
    dlg.finished.connect(lambda _: start_timer())
    dlg.show()


def _setup_menu() -> None:
    menu = QMenu("Popup Reviewer", mw)

    # Toggle on/off
    toggle_action = QAction("Enabled", mw)
    toggle_action.setCheckable(True)
    toggle_action.setChecked(get_config().get("enabled", True))

    def on_toggle(checked: bool) -> None:
        cfg = get_config()
        cfg["enabled"] = checked
        save_config(cfg)
        if checked:
            start_timer()
        else:
            stop_timer()

    toggle_action.toggled.connect(on_toggle)
    menu.addAction(toggle_action)

    menu.addSeparator()

    # Delay submenu
    delay_menu = QMenu("Delay", mw)
    delay_group = QActionGroup(mw)
    delay_group.setExclusive(True)
    current_interval = get_config().get("interval_minutes", 1)

    for label, minutes in DELAY_OPTIONS:
        action = QAction(label, mw)
        action.setCheckable(True)
        action.setChecked(abs(current_interval - minutes) < 0.01)
        action.setData(minutes)

        def on_delay(checked: bool, m: float = minutes) -> None:
            if not checked:
                return
            cfg = get_config()
            cfg["interval_minutes"] = m
            save_config(cfg)
            start_timer()

        action.toggled.connect(on_delay)
        delay_group.addAction(action)
        delay_menu.addAction(action)

    menu.addMenu(delay_menu)

    # Cards per session submenu
    cards_menu = QMenu("Cards per session", mw)
    cards_group = QActionGroup(mw)
    cards_group.setExclusive(True)
    current_cards = int(get_config().get("cards_per_session", 1))

    for n in CARDS_OPTIONS:
        action = QAction(str(n), mw)
        action.setCheckable(True)
        action.setChecked(current_cards == n)

        def on_cards(checked: bool, count: int = n) -> None:
            if not checked:
                return
            cfg = get_config()
            cfg["cards_per_session"] = count
            save_config(cfg)

        action.toggled.connect(on_cards)
        cards_group.addAction(action)
        cards_menu.addAction(action)

    menu.addMenu(cards_menu)

    mw.form.menuTools.addMenu(menu)


def _on_main_window_init() -> None:
    _setup_menu()
    start_timer()


gui_hooks.main_window_did_init.append(_on_main_window_init)
