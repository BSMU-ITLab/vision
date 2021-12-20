from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide2.QtCore import Qt, QObject, Signal, QSize, QPointF, QRectF, QMarginsF, QElapsedTimer, QPoint
from PySide2.QtGui import QPainter, QPixmap, QPalette, QColor, QPen, QPolygonF
from PySide2.QtWidgets import QWidget, QStyledItemDelegate, QStyle, QLineEdit

from bsmu.vision.widgets.images import icons_rc  # noqa: F401

if TYPE_CHECKING:
    from PySide2.QtCore import QAbstractItemModel, QModelIndex, QRect
    from PySide2.QtGui import QPaintEvent, QMouseEvent
    from PySide2.QtWidgets import QStyleOptionViewItem


class Visibility(QObject):
    def __init__(self, visible: bool = True, opacity: float = 1):
        super().__init__()

        self._visible = visible
        self._opacity = opacity

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        self._visible = value

    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float):
        self._opacity = value


class VisibilityDrawer:
    SLIDER_FOREGROUND_COLOR = QColor(213, 226, 240)
    SLIDER_THUMB_ALPHA = 155
    SLIDER_THUMB_PEN_COLOR = QColor(167, 194, 224, SLIDER_THUMB_ALPHA)
    SLIDER_THUMB_BRUSH_COLOR = QColor(182, 204, 228, SLIDER_THUMB_ALPHA)

    class Element(Enum):
        TOGGLE_ICON = auto()
        SLIDER = auto()
        TEXT = auto()
        VALUE_TEXT = auto()
        VALUE_BUTTON_UP = auto()
        VALUE_BUTTON_DOWN = auto()

    class EditMode(Enum):
        EDITABLE = auto()
        READ_ONLY = auto()

    def __init__(self, visibility: Visibility | None = None, draw_slider_thumb: bool = False):
        self._visibility = visibility
        self._draw_slider_thumb = draw_slider_thumb

        self._checked_toggle_icon = QPixmap(':/icons/eye-outlined.svg')
        self._unchecked_toggle_icon = QPixmap(':/icons/eye-outlined-crossed-out.svg')

        self._value_up_icon = QPixmap(':/icons/arrow-outlined-up.svg')
        self._value_down_icon = QPixmap(':/icons/arrow-outlined-down.svg')

        self._drawn_toggle_icon_rect_f = QRectF()
        self._drawn_value_text_rect_f = QRectF()
        self._drawn_value_up_button = QRectF()
        self._drawn_value_down_button = QRectF()

    @property
    def visibility(self) -> Visibility:
        return self._visibility

    @visibility.setter
    def visibility(self, value: Visibility):
        self._visibility = value

    @property
    def drawn_text_rect_f(self) -> QRectF:
        return self._drawn_value_text_rect_f

    def paint(self, painter: QPainter, rect: QRect, palette: QPalette, mode: EditMode):
        painter.save()

        if self._visibility.visible:
            toggle_icon = self._checked_toggle_icon
        else:
            toggle_icon = self._unchecked_toggle_icon

        # Draw slider foreground
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.SLIDER_FOREGROUND_COLOR)
        value_slider_foreground_rect_f = QRectF(rect)
        value_slider_foreground_width = self._visibility.opacity * value_slider_foreground_rect_f.width()
        value_slider_foreground_rect_f.setWidth(value_slider_foreground_width)
        painter.drawRect(value_slider_foreground_rect_f)

        margin_factor = 12
        margin = min(rect.width() / margin_factor, rect.height() / margin_factor)
        rect_f_without_margins = QRectF(rect)
        rect_f_without_margins -= QMarginsF(margin, margin, margin, margin)

        # Draw toggle icon
        toggle_icon_rect_f = QRectF(rect_f_without_margins)
        toggle_icon_rect_f.setWidth(toggle_icon_rect_f.width() / 4)
        toggle_icon = toggle_icon.scaled(
            int(toggle_icon_rect_f.width()),
            int(toggle_icon_rect_f.height()),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation)
        toggle_icon_top_left_y = toggle_icon_rect_f.y() + (toggle_icon_rect_f.height() - toggle_icon.height()) / 2
        toggle_icon_top_left_point_f = QPointF(toggle_icon_rect_f.x(), toggle_icon_top_left_y)
        painter.drawPixmap(toggle_icon_top_left_point_f, toggle_icon)
        self._drawn_toggle_icon_rect_f = QRectF(toggle_icon_top_left_point_f, toggle_icon.size())

        # Draw value up/down buttons
        value_up_down_buttons_rect_f = QRectF(rect_f_without_margins)
        value_up_down_buttons_rect_width = \
            min(rect_f_without_margins.width() / 6, rect_f_without_margins.height() / 1.5)
        value_up_down_buttons_rect_f.setX(value_up_down_buttons_rect_f.right() - value_up_down_buttons_rect_width)

        value_up_down_button_vert_space_from_center = margin / 2
        value_up_down_button_height = \
            value_up_down_buttons_rect_f.height() / 2 - value_up_down_button_vert_space_from_center

        value_up_button_rect_f = QRectF(value_up_down_buttons_rect_f)
        value_up_button_rect_f.setHeight(value_up_down_button_height)

        value_down_button_rect_f = QRectF(value_up_down_buttons_rect_f)
        value_down_button_rect_f.setTop(value_down_button_rect_f.bottom() - value_up_down_button_height)

        value_up_icon = self._value_up_icon.scaled(
            int(value_up_button_rect_f.width()),
            int(value_up_button_rect_f.height()),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation)
        value_up_top_left_y = value_up_button_rect_f.bottom() - value_up_icon.height()
        value_up_top_left_point_f = QPointF(value_up_button_rect_f.x(), value_up_top_left_y)
        painter.drawPixmap(value_up_top_left_point_f, value_up_icon)
        self._drawn_value_up_button = QRectF(value_up_top_left_point_f, value_up_icon.size())

        value_down_icon = self._value_down_icon.scaled(
            int(value_down_button_rect_f.width()),
            int(value_down_button_rect_f.height()),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation)
        painter.drawPixmap(value_down_button_rect_f.topLeft(), value_down_icon)
        self._drawn_value_down_button = QRectF(value_down_button_rect_f.topLeft(), value_down_icon.size())

        # Draw value text
        painter.setPen(QPen())
        text_rect = QRectF(rect_f_without_margins)
        text_rect.setRight(value_up_down_buttons_rect_f.left() - margin)
        self._drawn_value_text_rect_f = painter.drawText(
            text_rect, Qt.AlignRight | Qt.AlignVCenter, str(round(100 * self._visibility.opacity)))

        # Draw slider thumb
        if mode == VisibilityDrawer.EditMode.EDITABLE and self._draw_slider_thumb:
            thumb_pen_width = 1
            painter.setPen(QPen(self.SLIDER_THUMB_PEN_COLOR, thumb_pen_width, Qt.SolidLine))
            painter.setBrush(self.SLIDER_THUMB_BRUSH_COLOR)
            thumb_height = min(4 * margin, rect_f_without_margins.width() / 8)
            thumb_width = 0.8 * thumb_height
            half_thumb_width = thumb_width / 2
            thumb_straight_part_height = 0.6 * thumb_height
            top_thumb_points = [QPointF(value_slider_foreground_width - half_thumb_width, -thumb_pen_width),
                                QPointF(value_slider_foreground_width - half_thumb_width, thumb_straight_part_height),
                                QPointF(value_slider_foreground_width, thumb_height),
                                QPointF(value_slider_foreground_width + half_thumb_width, thumb_straight_part_height),
                                QPointF(value_slider_foreground_width + half_thumb_width, -thumb_pen_width)]
            bottom_thumb_points = [QPointF(p.x(), rect.height() - p.y()) for p in top_thumb_points]

            painter.setRenderHint(QPainter.Antialiasing)
            painter.drawConvexPolygon(QPolygonF(top_thumb_points))
            painter.drawConvexPolygon(QPolygonF(bottom_thumb_points))

        # Draw white translucent overlay, to emulate disabled editor
        if not self._visibility.visible:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 128))
            painter.drawRect(rect)

        painter.restore()

    def free_pos(self, pos: QPointF) -> bool:
        """
        Returns true, if pos is not in the icon or editable value rectangle
        """
        return not (self._drawn_toggle_icon_rect_f.contains(pos) or self._drawn_value_text_rect_f.contains(pos))

    def sizeHint(self) -> QSize:
        return QSize(96, 32)


class VisibilityEditor(QWidget):
    class EditedParameter(Enum):
        CHECK_BOX = auto()
        SLIDER = auto()
        VALUE = auto()

    editing = Signal()
    editing_finished = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self._visibility = None

        self._visibility_drawer = VisibilityDrawer()

        self.line_edit = QLineEdit(self)
        self.line_edit.setFrame(False)

        line_edit_palette = QPalette()
        line_edit_palette.setColor(QPalette.Base, Qt.transparent)
        self.line_edit.setPalette(line_edit_palette)
        # self.line_edit.setAttribute(Qt.WA_TranslucentBackground)

        self.line_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.line_edit.hide()

        self._pressed_on_free_space = False
        self._press_pos = QPoint()
        self._click_duration_timer = QElapsedTimer()

        self._edited_parameter = self.EditedParameter.CHECK_BOX

        #% self.setMouseTracking(True)
        self.setAutoFillBackground(True)

    def sizeHint(self) -> QSize:
        return self._visibility_drawer.sizeHint()

    @property
    def visibility(self) -> Visibility:
        return self._visibility

    @visibility.setter
    def visibility(self, value: Visibility):
        if self._visibility != value:
            self._visibility = value
            self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        self._visibility_drawer.visibility = self._visibility
        self._visibility_drawer.paint(painter, self.rect(), self.palette(), VisibilityDrawer.EditMode.EDITABLE)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._press_pos = event.pos()
        self._click_duration_timer.start()

        self._pressed_on_free_space = self._visibility_drawer.free_pos(event.pos())
        if self._pressed_on_free_space:
            self._edit_opacity_using_pos(event.x())
            self._edited_parameter = self.EditedParameter.SLIDER
        else:
            self._edited_parameter = self.EditedParameter.CHECK_BOX

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._pressed_on_free_space \
                or self._click_duration_timer.elapsed() > 500 \
                or (event.pos() - self._press_pos).manhattanLength() > 10:
            self._edit_opacity_using_pos(event.x())
            self._edited_parameter = self.EditedParameter.SLIDER

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        print('VisibilityEditor.mouseReleaseEvent')

        if self._edited_parameter == self.EditedParameter.CHECK_BOX:
            self.visibility.visible = not self.visibility.visible
            self.update()

        self.editing_finished.emit()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        print('VisibilityEditor.mouseDoubleClickEvent')

        self.line_edit.setText(str(round(100 * self._visibility.opacity)))
        self.line_edit.editingFinished.connect(self._finish_opacity_editing)
        text_rect = self._visibility_drawer.drawn_text_rect_f.toAlignedRect()
        text_rect.setX(text_rect.x() - text_rect.width())
        self.line_edit.setGeometry(text_rect)
        self.line_edit.selectAll()
        self.line_edit.show()
        self.line_edit.setFocus()

    def _finish_opacity_editing(self):
        self.line_edit.close()

    def _edit_opacity_using_pos(self, x: int):
        self.visibility.opacity = self._opacity_at_pos(x)
        self.update()

        self.editing.emit()

    def _opacity_at_pos(self, x: int) -> float:
        return min(max(0, x / self.rect().width()), 1)


class VisibilityDelegate(QStyledItemDelegate):
    def __init__(self, parent: QObject = None):
        super().__init__(parent)

        self._visibility_drawer = VisibilityDrawer()

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        if isinstance(index.data(), Visibility):
            if option.state & QStyle.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())

            self._visibility_drawer.visibility = index.data()
            self._visibility_drawer.paint(painter, option.rect, option.palette, VisibilityDrawer.EditMode.READ_ONLY)
        else:
            super().paint(painter, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        if isinstance(index.data(), Visibility):
            self._visibility_drawer.visibility = index.data()
            return self._visibility_drawer.sizeHint()
        return super().sizeHint(option, index)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        print('createEditor')
        if isinstance(index.data(), Visibility):
            print('createEditor for Visibility')
            visibility_editor = VisibilityEditor(parent)
            visibility_editor.editing.connect(self._commit)
            visibility_editor.editing_finished.connect(self._commit_and_close_editor)
            return visibility_editor
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor: QWidget, index: QModelIndex):
        print('setEditorData', index.row(), index.column())
        if isinstance(index.data(), Visibility):
            print('sed', index.data().visible, index.data().opacity)
            editor.visibility = index.data()
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        print('setModelData', index.row(), index.column())
        if isinstance(index.data(), Visibility):
            model.setData(index, editor.visibility)
        else:
            super().setModelData(editor, model, index)

    def _commit(self):
        editor = self.sender()
        self.commitData.emit(editor)

    def _commit_and_close_editor(self):
        editor = self.sender()
        self.commitData.emit(editor)
        self.closeEditor.emit(editor)
