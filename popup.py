import re

from anki.cards import Card
from aqt import mw
from aqt.qt import (
    QDialog,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QPushButton,
    QShortcut,
    Qt,
    QVBoxLayout,
    QWidget,
)
from aqt.sound import av_player
from aqt.webview import AnkiWebView


class PopupReviewer(QDialog):
    def __init__(self, card: Card, total: int = 1) -> None:
        super().__init__(mw)
        self._card = card
        self._total = total
        self._current = 1
        self._answer_shown = False

        self.setWindowTitle("Popup Reviewer")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumSize(600, 450)
        self.resize(mw.width(), mw.height())

        self._build_ui()
        self._show_front()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._progress_label = QLabel("")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._progress_label)
        self._update_progress_label()

        self._web = AnkiWebView(self)
        self._web.set_bridge_command(self._on_bridge_cmd, self)
        self._web.setMinimumHeight(300)
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
            btn.setStyleSheet(style)
            btn.clicked.connect(lambda _, e=ease: self._on_grade(e))
            grade_layout.addWidget(btn)
            self._grade_widget_buttons.append(btn)

        self._grade_widget = QWidget()
        self._grade_widget.setLayout(grade_layout)
        self._grade_widget.setVisible(False)
        layout.addWidget(self._grade_widget)

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
            self._progress_label.setText("")

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
        self._web.stdHtml(
            f'<div class="card">{clean_html}</div>'
            f"<style>{self._PLAY_BUTTON_CSS}</style>"
        )

    def _on_bridge_cmd(self, cmd: str) -> bool:
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
