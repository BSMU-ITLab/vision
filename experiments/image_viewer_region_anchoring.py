"""
Test viewer for image navigation and zoom behavior.

This standalone script isolates and verifies viewport handling logic:
- On window resize, the same physical region of the image remains visible,
  while its scale adjusts automatically.
- When switching between images of different sizes, the viewer restores
  the same relative portion of the image (e.g. full image, central area),
  so the user's point of view is preserved across images.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPixmap, QBrush, QColor
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent, QResizeEvent, QWheelEvent


@dataclass
class NormalizedViewRegion:
    min_ratio: float
    center: QPointF


SCRIPT_DIR = Path(__file__).resolve().parent
TEST_IMAGES_DIR = SCRIPT_DIR.parent / 'tests' / 'test-data' / 'images'


class ImageViewer(QGraphicsView):
    def __init__(self, image_paths: list[Path]):
        super().__init__()

        self._image_paths = image_paths
        self._current_image_index = 0

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._viewport_rect_in_scene: QRectF | None = None

        self._min_ratio: float | None = None
        self._anchor_rect: QRectF | None = None

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._anchor_rect_item: QGraphicsRectItem | None = None

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self._is_fitting_in_anchor_rect = False
        self._is_scene_rect_changing = False

    def load_image(self, path: Path):
        if self._pixmap_item is None:
            self._pixmap_item = QGraphicsPixmapItem()
            self._scene.addItem(self._pixmap_item)

        pixmap = QPixmap(path)
        if pixmap.isNull():
            print(f'Cannot load the image: {path}')
            return
        self._pixmap_item.setPixmap(pixmap)

        self.set_scrollable_scene_rect(self._pixmap_item.boundingRect())

    def _load_image_by_index(self, index: int):
        normalized_view_region = self.capture_normalized_view_region()

        path = self._image_paths[index]
        self.load_image(path)

        self.restore_normalized_view_region(normalized_view_region)

        self._current_image_index = index

    def capture_normalized_view_region(self) -> NormalizedViewRegion | None:
        if self._should_display_full_scene():
            return None  # Or we can return NormalizedViewRegion(1.0, QPointF(0.5, 0.5))

        if self._min_ratio is None:
            self._min_ratio = self._calculate_min_ratio()

        viewport_center_in_scene = self._viewport_rect_in_scene.center()
        normalized_center = QPointF(
            viewport_center_in_scene.x() / self.sceneRect().width(),
            viewport_center_in_scene.y() / self.sceneRect().height()
        )
        return NormalizedViewRegion(self._min_ratio, normalized_center)

    def restore_normalized_view_region(self, normalized_view_region: NormalizedViewRegion | None):
        scene_rect = self.sceneRect()
        if normalized_view_region is None:
            self._anchor_rect = scene_rect
        else:
            center = QPointF(normalized_view_region.center.x() * scene_rect.width(),
                             normalized_view_region.center.y() * scene_rect.height())
            self._anchor_rect = self._build_anchor_rect(normalized_view_region.min_ratio, center)

        self._draw_anchor_rect()
        self._fit_in_anchor_rect()

        if not self._should_display_full_scene():
            self._update_viewport_rect_in_scene()

    def set_scrollable_scene_rect(self, rect: QRectF):
        self._is_scene_rect_changing = True
        self.setSceneRect(rect)
        self._is_scene_rect_changing = False

    def _refresh_viewport_region(self):
        if self._is_fitting_in_anchor_rect or self._is_scene_rect_changing:
            return

        scene_rect = self.sceneRect()
        if scene_rect.isEmpty():
            return

        self._update_viewport_rect_in_scene()
        self._min_ratio = None
        self._anchor_rect = None

    def _update_viewport_rect_in_scene(self):
        viewport_rect = self.viewport().rect()
        self._viewport_rect_in_scene = self.mapToScene(viewport_rect).boundingRect()

    def _should_display_full_scene(self) -> bool:
        return self._viewport_rect_in_scene is None

    def _calculate_min_ratio(self) -> float:
        width_ratio = self._viewport_rect_in_scene.width() / self.sceneRect().width()
        height_ratio = self._viewport_rect_in_scene.height() / self.sceneRect().height()
        return min(width_ratio, height_ratio)

    def _build_anchor_rect(self, min_ratio: float, center: QPointF) -> QRectF:
        scene_rect = self.sceneRect()
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()

        new_width = scene_width * min_ratio
        new_height = scene_height * min_ratio

        # Build rectangle centered at `center`
        top_left = QPointF(
            center.x() - new_width / 2,
            center.y() - new_height / 2
        )
        bottom_right = QPointF(
            center.x() + new_width / 2,
            center.y() + new_height / 2
        )
        return QRectF(top_left, bottom_right)

    def _draw_anchor_rect(self):
        if self._anchor_rect is None:
            if self._anchor_rect_item is not None:
                self._anchor_rect_item.setRect(QRectF())
        else:
            if self._anchor_rect_item is None:
                self._anchor_rect_item = QGraphicsRectItem()
                self._anchor_rect_item.setBrush(QColor(0, 0, 255, 100))
                self._scene.addItem(self._anchor_rect_item)
            self._anchor_rect_item.setRect(self._anchor_rect)

    def _determine_anchor_rect(self) -> QRectF | None:
        """Decide which anchor rect should be used based on current state."""
        scene_rect = self.sceneRect()
        if scene_rect.isEmpty():
            return None

        if self._should_display_full_scene():
            return scene_rect

        self._min_ratio = self._calculate_min_ratio()
        return self._build_anchor_rect(self._min_ratio, self._viewport_rect_in_scene.center())

    def _fit_in_anchor_rect(self):
        self._is_fitting_in_anchor_rect = True

        if self._anchor_rect is None:
            self._anchor_rect = self._determine_anchor_rect()
            self._draw_anchor_rect()

        if self._anchor_rect is not None:
            self.fitInView(self._anchor_rect, Qt.AspectRatioMode.KeepAspectRatio)

        self._is_fitting_in_anchor_rect = False

    def resizeEvent(self, event: QResizeEvent):
        if self._pixmap_item:
            self._fit_in_anchor_rect()

        super().resizeEvent(event)

    def scrollContentsBy(self, dx: int, dy: int):
        super().scrollContentsBy(dx, dy)

        self._refresh_viewport_region()

    def wheelEvent(self, event: QWheelEvent):
        if self._pixmap_item is None:
            return

        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)

        self._refresh_viewport_region()

    def keyPressEvent(self, event: QKeyEvent):
        match event.key():
            case Qt.Key.Key_Left:
                prev_image_index = (self._current_image_index - 1) % len(self._image_paths)
                self._load_image_by_index(prev_image_index)
            case Qt.Key.Key_Right:
                next_image_index = (self._current_image_index + 1) % len(self._image_paths)
                self._load_image_by_index(next_image_index)
            case Qt.Key.Key_Up:
                # Expand scene rect artificially
                r = self._scene.sceneRect()
                delta = 150
                r.adjust(-delta, -delta, delta, delta)
                self._scene.setSceneRect(r)
                # self.set_scrollable_scene_rect(r)
            case Qt.Key.Key_Down:
                random_rect = QRectF(-300, -300, 200, 200)
                self._scene.addRect(random_rect, brush=QBrush(Qt.GlobalColor.green))
                # self.set_scrollable_scene_rect(self._scene.sceneRect())
            case _:
                super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)

    first_image_path = TEST_IMAGES_DIR / '01-eye-fundus-8UC3.png'
    image_paths = [
        first_image_path,
        TEST_IMAGES_DIR / '04-eye-fundus-8UC3.jpg',
    ]
    viewer = ImageViewer(image_paths)
    viewer.setWindowTitle('Image Viewer Test')
    viewer.resize(600, 200)

    viewer.load_image(first_image_path)

    viewer.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
