from __future__ import annotations

from PySide2.QtCore import QObject, Signal, QRectF, QPoint
from PySide2.QtGui import QPainter, QImage
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


        self.image_rgba = None
        self.qimage = None

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
        self.image_rgba = image_converter.converted_to_rgba(self.image.array)
        return image_converter.numpy_rgba_image_to_qimage(self.image_rgba)
        # return self.qimage


        # if self._displayed_image_cache is None:
        #     displayed_rgba_array = image_converter.converted_to_rgba(self.image.array)
        #     self._displayed_image_cache = image_converter.numpy_rgba_image_to_qimage(displayed_rgba_array)
        #     print('cashe')
        # return self._displayed_image_cache

        '''
        if self._displayed_image_cache is None:
            if self.image.palette is None:
                print('a')
                # displayed_rgba_array = image_converter.converted_to_normalized_uint8(self.image.array)
                print('b')
                # displayed_rgba_array = image_converter.converted_to_rgba(displayed_rgba_array)
                displayed_rgba_array = image_converter.converted_to_rgba(self.image.array)
                print('c')
            # else:
            #     displayed_rgba_array = self.colormap.colored_premultiplied_image(self.image.array)
            self._displayed_image_cache = image_converter.numpy_rgba_image_to_qimage(displayed_rgba_array)
            print('cashe')
        return self._displayed_image_cache
        '''

    def _on_image_updated(self):
        print('on_image_updated (image array updated or layer image changed) !!!!!!!!!!!!!')
        self._displayed_image_cache = None
        self.updated.emit(self.image)


class _LayeredImageItem(QGraphicsItem):
    def __init__(self):
        super().__init__()

        self.layers = []

        self.img = None

    def boundingRect(self):
        if self.layers:
            image = self.layers[0].displayed_image
            return QRectF(image.rect())
        else:
            return QRectF()

    def add_layer(self, image: FlatImage = None, name: str = ''):
        layer = _ImageItemLayer(image, name)
        self.layers.append(layer)
        # Calling update() several times normally results in just one paintEvent() call.
        # See QWidget::update() documentation.
        layer.updated.connect(self.update)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for layer in self.layers:
            if layer.image is not None and layer.visible:
                painter.setOpacity(layer.opacity)
                print('draw', layer.displayed_image)

                # self.img = QImage('d:/Projects/vision/vision/tests/images/spacex.jpg')
                # print(self.img.size())
                #
                # painter.drawImage(QPoint(0, 0), self.img) #layer.displayed_image)

                # image_rgba = image_converter.converted_to_rgba(layer.image.array)
                # qimage = image_converter.numpy_rgba_image_to_qimage(image_rgba)

                painter.drawImage(QPoint(0, 0), layer.displayed_image)
                print('draw2')


class LayeredImageViewer(DataViewer):
    # before_image_changed = Signal()
    # image_changed = Signal()
    # colormap_active_class_changed = Signal(int)

    def __init__(self, image: FlatImage = None):
        super().__init__(image)

        print('FlatImageViewer __init__')

        self.layered_image_item = _LayeredImageItem()

        self.graphics_scene = QGraphicsScene()
        self.graphics_scene.addItem(self.layered_image_item)

        self.graphics_view = GraphicsView(self.graphics_scene, zoomable=False)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.graphics_view)
        self.setLayout(grid_layout)

        if image is not None:
            print('shape:', image.array.shape)
            self.layered_image_item.add_layer(image)

    def add_layer(self, image: FlatImage = None, name: str = ''):
        self.layered_image_item.add_layer(image, name)
