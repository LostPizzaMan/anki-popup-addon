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

    def _render(self, html: str) -> None:
        note_type_css = self._card.note_type().get("css", "")
        self._web.stdHtml(f'<style>{note_type_css}</style><div class="card">{html}</div>')

    def _show_front(self) -> None:
        self._answer_shown = False
        self._render(self._card.question())
        self._show_answer_btn.setVisible(True)
        self._grade_widget.setVisible(False)

    def _on_show_answer(self) -> None:
        if self._answer_shown:
            return
        self._answer_shown = True
        self._render(self._card.answer())
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
