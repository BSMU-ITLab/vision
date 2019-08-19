from __future__ import annotations

from PySide2.QtCore import QObject, Signal, QRectF
from PySide2.QtGui import QPainter
from PySide2.QtWidgets import QGridLayout, QGraphicsScene, QGraphicsItem

from bsmu.vision_core.image import FlatImage
import bsmu.vision_core.converters.image as image_converter
from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision.widgets.viewers.graphics_view import GraphicsView


class _ImageItemLayer(QObject):
    max_id = 0

    updated = Signal(FlatImage)

    def __init__(self, image: FlatImage = None, name: str = '',
                 visible: bool = True, opacity: float = 1):
        super().__init__()
        self.id = _ImageItemLayer.max_id
        _ImageItemLayer.max_id += 1

        self._image = None
        self.image = image #if image is not None else Image()
        self.name = name if name else 'Layer ' + str(self.id)
        self.visible = visible
        self.opacity = opacity

        self._displayed_image_cache = None
        # Store numpy array's data, because QImage uses it without copying,
        # and QImage will crash if it's data buffer will be deleted
        self._displayed_array_data = None

    @property
    def image_path(self):
        return self.image.path

    @property  # TODO: this is slow. If we need only setter, there are alternatives without getter
    def image(self):
        return self._image

    @image.setter
    def image(self, value):
        if self._image != value:
            self._image = value
            self._on_image_updated()
            self._image.updated.connect(self._on_image_updated)

    @property
    def displayed_image(self):
        if self._displayed_image_cache is None:
            if self.image.palette is None:
                # displayed_rgba_array = image_converter.converted_to_normalized_uint8(self.image.array)
                # displayed_rgba_array = image_converter.converted_to_rgba(displayed_rgba_array)

                displayed_rgba_array = image_converter.converted_to_rgba(self.image.array)
            else:
                # displayed_rgba_array = self.colormap.colored_premultiplied_image(self.image.array)
                raise NotImplementedError

            self._displayed_array_data = displayed_rgba_array.data
            self._displayed_image_cache = image_converter.numpy_rgba_image_to_qimage(displayed_rgba_array)
        return self._displayed_image_cache

    def _on_image_updated(self):
        print('_ImageItemLayer _on_image_updated (image array updated or layer image changed)')
        self._displayed_image_cache = None
        self.updated.emit(self.image)


class _LayeredImageItem(QGraphicsItem):
    def __init__(self, parent: QGraphicsItem = None):
        super().__init__(parent)

        self.layers = []

        self._bounding_rect = QRectF()

    def boundingRect(self):
        return self._bounding_rect

    def add_layer(self, image: FlatImage = None, name: str = ''):
        layer = _ImageItemLayer(image, name)
        self.layers.append(layer)
        # Calling update() several times normally results in just one paintEvent() call.
        # See QWidget::update() documentation.
        layer.updated.connect(self.update)

        if len(self.layers) == 1:  # If was added first layer
            self.update_bounding_rect()

    def update_bounding_rect(self):
        self.prepareGeometryChange()

        if self.layers:
            image = self.layers[0].displayed_image
            image_rect = image.rect()
            # self._bounding_rect = QRectF(image_rect)  # center of the item will be in top left point of image
            self._bounding_rect = QRectF(-image_rect.width() / 2, -image_rect.height() / 2,
                                         image_rect.width(), image_rect.height())
        else:
            self._bounding_rect = QRectF()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for layer in self.layers:
            if layer.image is not None and layer.visible:
                painter.setOpacity(layer.opacity)
                painter.drawImage(self._bounding_rect.topLeft(), layer.displayed_image)


class LayeredImageViewer(DataViewer):
    # before_image_changed = Signal()
    # image_changed = Signal()
    # colormap_active_class_changed = Signal(int)

    def __init__(self, image: FlatImage = None, zoomable=True):
        super().__init__(image)

        print('FlatImageViewer __init__')

        self.layered_image_item = _LayeredImageItem()

        self.graphics_scene = QGraphicsScene()
        self.graphics_scene.addItem(self.layered_image_item)

        self.graphics_view = GraphicsView(self.graphics_scene, zoomable)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.graphics_view)
        self.setLayout(grid_layout)

        if image is not None:
            print('shape:', image.array.shape)
            self.add_layer(image)

    def add_layer(self, image: FlatImage = None, name: str = ''):
        self.layered_image_item.add_layer(image, name)

    def center(self):
        print('center')
        self.graphics_view.centerOn(self.layered_image_item)
