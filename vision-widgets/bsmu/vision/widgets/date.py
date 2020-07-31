from __future__ import annotations

from PySide2.QtCore import QDate
from PySide2.QtWidgets import QWidget, QDateEdit


class DateEditWidget(QDateEdit):
    def __init__(self, date: QDate = QDate(), embedded: bool = False, parent: QWidget = None):
        super().__init__(date, parent)

        self._embedded = embedded

        if self._embedded:
            self.setFrame(False)
