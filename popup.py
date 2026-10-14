import re

from anki.cards import Card
from aqt import mw
from aqt.qt import (
    QDialog,
    QGuiApplication,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QPushButton,
    QRect,
    QShortcut,
    QSizeGrip,
    Qt,
    QVBoxLayout,
    QWidget,
)
from aqt.sound import av_player
from aqt.webview import AnkiWebView


COMPACT_SIZE = (360, 300)
COMPACT_MARGIN = 16
FIT_MAX_SCREEN_FRACTION = 0.7
FIT_MIN_ZOOM = 0.7

# Reports the card's natural size (CSS px) so Python can zoom/grow the window
_FIT_SCRIPT = """<script>
(function (pageId) {
    var el = document.getElementById("popup-fit");
    var last = "";
    function report() {
        var w = Math.ceil(Math.max(el.scrollWidth, el.getBoundingClientRect().width));
        var h = Math.ceil(Math.max(el.scrollHeight, el.getBoundingClientRect().height)
                          + el.offsetTop * 2);
        var key = w + ":" + h;
        if (key === last) return;
        last = key;
        pycmd("size:" + pageId + ":" + key);
    }
    new ResizeObserver(report).observe(el);
    window.addEventListener("load", report);
    report();
})(%d);
</script>
"""


class _DragHandle(QWidget):
    """Header bar that moves its (frameless) top-level window when dragged."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._offset = None

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._offset = e.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, e) -> None:
        if self._offset is not None:
            self.window().move(e.globalPosition().toPoint() - self._offset)

    def mouseReleaseEvent(self, e) -> None:
        self._offset = None


class _Grip(QSizeGrip):
    """Size grip that reports when the user finishes resizing."""

    def __init__(self, parent: QWidget, on_resized) -> None:
        super().__init__(parent)
        self._on_resized = on_resized

    def mouseReleaseEvent(self, e) -> None:
        super().mouseReleaseEvent(e)
        self._on_resized()


class PopupReviewer(QDialog):
    def __init__(
        self, card: Card, total: int = 1, compact: bool = False, autofit: bool = True
    ) -> None:
        # Compact mode has no parent so that showing/closing it doesn't bring
        # Anki's main window forward (Windows activates a child window's owner)
        super().__init__(None if compact else mw)
        self._card = card
        self._total = total
        self._current = 1
        self._answer_shown = False
        self._compact = compact
        self._autofit = compact and autofit
        self._zoom = 1.0
        self._page_id = 0

        self.setWindowTitle("Popup Reviewer")
        if compact:
            self.setWindowFlags(
                Qt.WindowType.Tool
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
            )
            # Don't steal focus from whatever the user is typing in
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setObjectName("popupCompact")
            self.setStyleSheet("#popupCompact { border: 1px solid #888; }")
            self.setMinimumSize(260, 180)
            self._place_compact()
            # User-chosen height; auto-fit never shrinks the window below it
            self._base_h = self.height()
        else:
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
            self.setMinimumSize(600, 450)
            self.resize(mw.width(), mw.height())

        self._build_ui()
        self._show_front()

    def _place_compact(self) -> None:
        geo = (mw.addonManager.getConfig(__name__) or {}).get("compact_geometry")
        if isinstance(geo, list) and len(geo) == 4:
            rect = QRect(*geo)
            if QGuiApplication.screenAt(rect.center()) is not None:
                self.setGeometry(rect)
                return

        w, h = COMPACT_SIZE
        area = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(w, h)
        self.move(area.right() - w - COMPACT_MARGIN, area.bottom() - h - COMPACT_MARGIN)

    def _save_compact_geometry(self) -> None:
        cfg = mw.addonManager.getConfig(__name__) or {}
        g = self.geometry()
        # Save the user's size, not the auto-grown one, keeping the bottom edge
        h = self._base_h if self._autofit else g.height()
        cfg["compact_geometry"] = [g.x(), g.bottom() + 1 - h, g.width(), h]
        mw.addonManager.writeConfig(__name__, cfg)

    def _apply_zoom(self) -> None:
        # Go through the page: AnkiWebView overrides zoomFactor()/setZoomFactor()
        self._web.page().setZoomFactor(self._zoom)

    def _on_user_resized(self) -> None:
        self._base_h = self.height()

    def _fit_to_content(self, content_w: int, content_h: int) -> None:
        """Zoom to fit width, grow upward to fit height, then zoom further if capped."""
        if content_w <= 0 or content_h <= 0:
            return
        area = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        chrome_h = self.height() - self._web.height()
        max_h = max(self._base_h, int(area.height() * FIT_MAX_SCREEN_FRACTION))

        # Within a card, zoom only goes down and height only goes up (reset per
        # card). Resizing reflows the card (wrapping, scrollbars), so allowing
        # both directions can make it flip back and forth between two sizes.
        zoom = max(FIT_MIN_ZOOM, min(self._zoom, self._web.width() / content_w))
        if content_h * zoom <= self._web.height() + 2:
            # Already fits. Templates that stretch to 100vh always measure as
            # the viewport height, so don't treat that as needing more room.
            new_h = self.height()
        else:
            needed_h = int(content_h * zoom) + chrome_h + 4
            if needed_h > max_h:
                zoom = max(FIT_MIN_ZOOM, min(zoom, (max_h - chrome_h - 4) / content_h))
                needed_h = max_h
            new_h = max(self.height(), needed_h)

        self._zoom = zoom
        self._apply_zoom()

        self._set_height(new_h)

    def _set_height(self, new_h: int) -> None:
        """Resize keeping the bottom edge anchored."""
        if new_h == self.height():
            return
        area = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        g = self.geometry()
        top = max(area.top(), g.bottom() + 1 - new_h)
        self.setGeometry(g.x(), top, g.width(), new_h)

    def _reset_fit(self) -> None:
        """Back to the user's size and 100% zoom, so each card fits from scratch."""
        self._zoom = 1.0
        self._apply_zoom()
        self._set_height(self._base_h)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._progress_label = QLabel("")
        if self._compact:
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(4)

            header = _DragHandle(self)
            header.setCursor(Qt.CursorShape.SizeAllCursor)
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.addWidget(self._progress_label)
            header_layout.addStretch(1)
            close_btn = QPushButton("✕")
            close_btn.setFlat(True)
            close_btn.setFixedWidth(24)
            close_btn.setCursor(Qt.CursorShape.ArrowCursor)
            close_btn.clicked.connect(self.reject)
            header_layout.addWidget(close_btn)
            layout.addWidget(header)
        else:
            self._progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(self._progress_label)
        self._update_progress_label()

        self._web = AnkiWebView(self)
        self._web.set_bridge_command(self._on_bridge_cmd, self)
        self._web.setMinimumHeight(80 if self._compact else 300)
        if self._autofit:
            # Anki resets zoom when a page loads, so re-apply ours afterwards
            self._web.loadFinished.connect(lambda _: self._apply_zoom())
        layout.addWidget(self._web, stretch=1)

        self._show_answer_btn = QPushButton("Show Answer")
        self._show_answer_btn.clicked.connect(self._on_show_answer)
        layout.addWidget(self._show_answer_btn)

        grade_layout = QHBoxLayout()
        self._grade_widget_buttons = []
        for label, ease, style in [
            ("Again", 1, "background-color: #c0392b; color: white;"),
            ("Hard", 2, ""),
            ("Good", 3, "background-color: #27ae60; color: white;"),
            ("Easy", 4, "background-color: #2980b9; color: white;"),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(style + " padding: 4px 6px;")
            btn.clicked.connect(lambda _, e=ease: self._on_grade(e))
            grade_layout.addWidget(btn)
            self._grade_widget_buttons.append(btn)

        self._grade_widget = QWidget()
        self._grade_widget.setLayout(grade_layout)
        self._grade_widget.setVisible(False)
        layout.addWidget(self._grade_widget)

        if self._compact:
            layout.addWidget(
                _Grip(self, self._on_user_resized),
                0,
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
            )

        QShortcut(QKeySequence("Return"), self).activated.connect(self._on_show_answer)
        QShortcut(QKeySequence("Space"), self).activated.connect(self._on_show_answer)
        for ease in range(1, 5):
            QShortcut(QKeySequence(str(ease)), self).activated.connect(
                lambda e=ease: self._on_grade(e)
            )

    def _update_progress_label(self) -> None:
        if self._total > 1:
            self._progress_label.setText(f"{self._current} / {self._total}")
        else:
            self._progress_label.setText("Popup Reviewer" if self._compact else "")

    _REPLAY_BUTTON = """\
        <a class="replay-button soundLink" href="#" onclick="pycmd('play:{side}:{idx}'); return false;">
            <svg class="playImage" viewBox="0 0 64 64" version="1.1">
                <circle cx="32" cy="32" r="29"></circle>
                <path d="M56.502,32.301l-37.502,20.101l0.329,-40.804l37.173,20.703Z"></path>
            </svg>
        </a>
    """

    def _av_tag_to_button(self, m: re.Match) -> str:
        return self._REPLAY_BUTTON.format(side=m.group(1), idx=m.group(2))

    _PLAY_BUTTON_CSS = """\
        .replay-button {
            text-decoration: none;
            display: inline-flex;
            vertical-align: middle;
            margin: 3px;
        }
        .replay-button svg {
            width: 40px;
            height: 40px;
        }
        .replay-button svg circle {
            fill: #fff;
            stroke: #414141;
        }
        .replay-button svg path {
            fill: #414141;
        }
    """

    def _render(self, html: str) -> None:
        clean_html = re.sub(r"\[anki:play:([qa]):(\d+)\]", self._av_tag_to_button, html)
        body = f'<div class="card">{clean_html}</div>'
        if self._autofit:
            self._page_id += 1
            body = (
                f'<div id="popup-fit" style="display: flow-root">{body}</div>'
                + _FIT_SCRIPT % self._page_id
            )
        self._web.stdHtml(f"<style>{self._PLAY_BUTTON_CSS}</style>{body}")

    def _on_bridge_cmd(self, cmd: str) -> bool:
        if cmd.startswith("size:"):
            if self._autofit:
                try:
                    page_id, w, h = (int(float(v)) for v in cmd.split(":")[1:4])
                except ValueError:
                    return True
                # Ignore reports from a page that has since been replaced
                if page_id == self._page_id:
                    self._fit_to_content(w, h)
            return True
        if not cmd.startswith("play:"):
            return False
        parts = cmd.split(":")
        if len(parts) != 3:
            return False
        side, idx = parts[1], int(parts[2])
        tags = self._card.question_av_tags() if side == "q" else self._card.answer_av_tags()
        if 0 <= idx < len(tags):
            av_player.play_tags([tags[idx]])
        return True

    def _show_front(self) -> None:
        self._answer_shown = False
        if self._autofit:
            self._reset_fit()
        self._render(self._card.question())
        av_player.play_tags(self._card.question_av_tags())
        self._show_answer_btn.setVisible(True)
        self._grade_widget.setVisible(False)

    def _on_show_answer(self) -> None:
        if self._answer_shown:
            return
        self._answer_shown = True
        self._render(self._card.answer())
        av_player.play_tags(self._card.answer_av_tags())
        self._show_answer_btn.setVisible(False)
        self._grade_widget.setVisible(True)

    def _on_grade(self, ease: int) -> None:
        if not self._answer_shown:
            return
        try:
            mw.col.sched.answerCard(self._card, ease)
            mw.autosave()
        except Exception:
            pass

        if self._current < self._total:
            next_card = mw.col.sched.getCard()
            if next_card is not None:
                self._card = next_card
                self._current += 1
                self._update_progress_label()
                self._show_front()
                return

        self.accept()

    def done(self, result: int) -> None:
        av_player.stop_and_clear_queue()
        if self._compact:
            self._save_compact_geometry()
        super().done(result)
