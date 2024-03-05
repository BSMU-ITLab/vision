from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QPointF, QRect, QTime, QTimer
from PySide6.QtGui import QPainter, QLinearGradient, QColor, QPalette
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QStyleOptionProgressBar, QApplication, QStyle, QStyledItemDelegate

from bsmu.vision.core.task import Task
from bsmu.vision.widgets.images import icons_rc  # noqa: F401

if TYPE_CHECKING:
    from typing import Final

    from PySide6.QtCore import QObject, QModelIndex
    from PySide6.QtWidgets import QStyleOptionViewItem


class ProgressDelegate(QStyledItemDelegate):
    BACKGROUND_COLOR = QColor(255, 235, 208)
    FOREGROUND_COLOR = QColor(204, 228, 247)

    BUSY_INDICATOR_SPEED_FACTOR = 0.1
    BUSY_INDICATOR_UPDATE_PERIOD = 16  # milliseconds

    def __init__(self, draw_icon_on_right_side: bool = True, parent: QObject = None):
        super().__init__(parent)

        self._draw_icon_on_right_side = draw_icon_on_right_side

        self._check_mark_icon_svg = QSvgRenderer(':/icons/check-mark.svg')
        self._check_mark_icon_svg.setAspectRatioMode(Qt.KeepAspectRatio)

        self._busy_indicator_item_indexes = set()
        self._is_updating_items_with_busy_indicators = False

        self._busy_indicator_update_timer = QTimer()
        self._busy_indicator_update_timer.timeout.connect(self._update_items_with_busy_indicators)
        self._busy_indicator_update_timer.start(self.BUSY_INDICATOR_UPDATE_PERIOD)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        task = index.data()
        if isinstance(task, Task):
            # Draw only QStyle.CE_ProgressBarGroove using QStyleOptionProgressBar
            # because if to draw full QStyle.CE_ProgressBar, we can change its colors
            # only when QProgressBar created and passed into QApplication.style().drawControl
            # and style sheet has to be set for all application (not only for some widget).
            # Busy indicator is not working with other methods, like this one:
            # https://stackoverflow.com/questions/10630360/customized-color-on-progressbar-delegate/10630476#10630476
            progress_option = QStyleOptionProgressBar()
            progress_option.rect = option.rect
            progress_option.minimum = 0
            progress_option.maximum = 100
            progress_option.progress = task.progress
            text = f'{task.name}: {task.progress}%' if task.progress_known else f'{task.name}'
            progress_option.text = text
            progress_option.textAlignment = Qt.AlignCenter
            progress_option.textVisible = True
            palette = progress_option.palette
            # Use the same text color even if progress is more than 50
            palette.setColor(QPalette.HighlightedText, palette.color(QPalette.Text))
            progress_option.palette = palette

            QApplication.style().drawControl(QStyle.CE_ProgressBarGroove, progress_option, painter)

            painter.save()

            GROOVE_BORDER_WIDTH: Final[int] = 1
            # TODO: we have to get `GROOVE_BORDER_WIDTH` value somehow from QStyle.CE_ProgressBarGroove
            #  or draw the groove yourself
            # Set clipping rectangle to avoid drawing over the groove border
            painter.setClipRect(
                progress_option.rect.adjusted(
                    GROOVE_BORDER_WIDTH, GROOVE_BORDER_WIDTH, -GROOVE_BORDER_WIDTH, -GROOVE_BORDER_WIDTH))

            if task.is_finished:
                self._draw_finished_task_with_icon(painter, progress_option)
                self._discard_busy_indicator_item(index)
            else:
                self._draw_background(painter, progress_option)
                if task.progress_known:
                    self._draw_completed_progress_chunk(painter, progress_option)
                    self._discard_busy_indicator_item(index)
                else:
                    self._draw_busy_indicator(painter, progress_option)
                    if not self._is_updating_items_with_busy_indicators:
                        self._busy_indicator_item_indexes.add(index)

                self._draw_label(painter, progress_option)

            painter.restore()
        else:
            super().paint(painter, option, index)

    def _discard_busy_indicator_item(self, index: QModelIndex):
        # Size of set cannot be changed during iteration, so we use next flag
        if not self._is_updating_items_with_busy_indicators:
            self._busy_indicator_item_indexes.discard(index)

    def _update_items_with_busy_indicators(self):
        model = self.parent().model()
        for index in self._busy_indicator_item_indexes:
            self._is_updating_items_with_busy_indicators = True
            # Emitting the next signal will call the `paint` method
            model.dataChanged.emit(index, index)
            self._is_updating_items_with_busy_indicators = False

    def _draw_finished_task_with_icon(self, painter: QPainter, progress_option: QStyleOptionProgressBar):
        painter.save()

        painter.setPen(Qt.NoPen)
        painter.setBrush(self.FOREGROUND_COLOR)
        painter.drawRect(progress_option.rect)

        painter.restore()

        # Draw label up to finished task icon (icon will be rendered over the label)
        self._draw_label(painter, progress_option)

        icon_rect = QRect(progress_option.rect)
        X_MARGIN_FACTOR = 0.02
        Y_MARGIN_FACTOR = 0.16
        x_margin = X_MARGIN_FACTOR * icon_rect.width()
        y_margin = Y_MARGIN_FACTOR * icon_rect.height()
        icon_rect.adjust(x_margin, y_margin, -x_margin, -y_margin)

        icon_rect_width = min(icon_rect.height(), icon_rect.width() / 4)
        if self._draw_icon_on_right_side:
            icon_rect.setX(icon_rect.right() - icon_rect_width)
        else:
            icon_rect.setWidth(icon_rect_width)

        self._check_mark_icon_svg.render(painter, icon_rect)

    @classmethod
    def _draw_background(cls, painter: QPainter, progress_option: QStyleOptionProgressBar):
        painter.save()

        painter.setPen(Qt.NoPen)
        painter.setBrush(cls.BACKGROUND_COLOR)
        painter.drawRect(progress_option.rect)

        painter.restore()

    @classmethod
    def _draw_completed_progress_chunk(cls, painter: QPainter, progress_option: QStyleOptionProgressBar):
        painter.save()

        painter.setPen(Qt.NoPen)
        painter.setBrush(cls.FOREGROUND_COLOR)

        # Get a copy of `progress_option.rect`
        completed_rect = QRect(progress_option.rect)
        completed_rect.setWidth(progress_option.progress / 100 * completed_rect.width())
        painter.drawRect(completed_rect)

        painter.restore()

    @classmethod
    def _draw_busy_indicator(cls, painter: QPainter, progress_option: QStyleOptionProgressBar):
        """ Draw a custom busy indicator animation on the groove. """

        painter.save()

        t = QTime.currentTime().msecsSinceStartOfDay()
        indicator_width = progress_option.rect.width() // 2
        # Calculate the position of the rectangle based on the time.
        # Rectangle of the busy indicator should start movement at `- indicator_width` position
        # and should end movement at `progress_option.rect.width() + indicator_width`.
        x = (t * cls.BUSY_INDICATOR_SPEED_FACTOR // 1) % (progress_option.rect.width() + indicator_width) \
            - indicator_width

        gradient = QLinearGradient(QPointF(x, 0), QPointF(x + indicator_width, 0))
        gradient.setColorAt(0, Qt.transparent)
        gradient.setColorAt(0.3, cls.FOREGROUND_COLOR)
        gradient.setColorAt(0.7, cls.FOREGROUND_COLOR)
        gradient.setColorAt(1, Qt.transparent)

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRect(x, progress_option.rect.y(), indicator_width, progress_option.rect.height())

        painter.restore()

    @classmethod
    def _draw_label(cls, painter: QPainter, progress_option: QStyleOptionProgressBar):
        QApplication.style().drawControl(QStyle.CE_ProgressBarLabel, progress_option, painter)
