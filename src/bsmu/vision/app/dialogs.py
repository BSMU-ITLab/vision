from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox, QStyle

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from bsmu.vision.app.plugin_manager import PluginLoadError


class PluginLoadErrorDialog(QDialog):
    """Dialog for displaying fatal plugin loading errors."""

    def __init__(self, errors: list[PluginLoadError], parent: QWidget = None) -> None:
        super().__init__(parent)

        self._errors = errors
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle('Plugin Loading Error')
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical))

        main_layout = QVBoxLayout(self)

        error_count = len(self._errors)
        main_message = (
            f'Failed to load {error_count} plugin(s).\n\n'
            f'The application cannot start in a stable state and will now exit.\n'
            f'Please check the log file.'
        )
        main_label = QLabel(main_message)
        main_label.setWordWrap(True)
        main_layout.addWidget(main_label)

        details_text = QTextEdit()
        details_text.setReadOnly(True)
        details_text.setPlainText(self._format_detailed_text())

        font = QFont('Monospace')
        font.setStyleHint(QFont.StyleHint.Monospace)
        details_text.setFont(font)

        main_layout.addWidget(details_text, stretch=1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

        self.resize(700, 500)

    def _format_detailed_text(self) -> str:
        """Format errors into a readable plain-text report."""
        error_count = len(self._errors)
        lines = [
            f'--- Detailed Error Report ({error_count} total) ---',
            '',
        ]

        for i, error in enumerate(self._errors, start=1):
            lines.extend([
                f'Error {i}:',
                f'  Plugin:   {error.plugin_name}',
                f'  Category: {error.category}',
                f'  Details:  {error.details}',
                '',
            ])
            if i < error_count:
                lines.extend(['---', ''])

        lines.extend([
            '---',
            'Tip: You can copy this text and send it to support if needed.',
        ])

        return '\n'.join(lines)
