from __future__ import annotations

import numpy as np
from PySide2.QtCore import QObject, Qt, Signal, QRectF, QPointF
from PySide2.QtGui import QPainter, QImage
from PySide2.QtWidgets import QGridLayout, QGraphicsScene, QGraphicsObject, QGraphicsItem

import bsmu.vision_core.converters.image as image_converter
from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision.widgets.viewers.graphics_view import GraphicsView
from bsmu.vision_core.image.base import FlatImage
from bsmu.vision_core.image.layered import ImageLayer, LayeredImage

DEFAULT_LAYER_OPACITY = 1


class _DisplayedImageLayer(QObject):
    image_updated = Signal(FlatImage)
    visibility_updated = Signal()

    def __init__(self, image_layer: ImageLayer, visible: bool = True, opacity: float = DEFAULT_LAYER_OPACITY):
        super().__init__()

        self._image_layer = image_layer
        self._image_layer.image_updated.connect(self.image_updated)
        self._visible = visible
        self._opacity = opacity

        self._displayed_qimage_cache = None
        # Store numpy array's data, because QImage uses it without copying,
        # and QImage will crash if it's data buffer will be deleted
        self._displayed_pixels_data = None

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        if self._visible != value:
            self._visible = value
            self.visibility_updated.emit()

    @property
    def opacity(self) -> float:
        return self._opacity

    @property
    def image(self) -> FlatImage:
        return self._image_layer.image

    @property
    def image_palette(self) -> Palette:
        return self._image_layer.image_palette

    @property
    def image_pixels(self) -> np.ndarray:
        return self._image_layer.image_pixels

    @property
    def image_path(self) -> Path:
        return self._image_layer.image_path

    @property
    def image_path_name(self) -> str:
        return self._image_layer.image_path_name

    @property
    def name(self) -> str:
        return self._image_layer.name

    @property
    def displayed_image(self):
        if self._displayed_qimage_cache is None:
            if self.image_palette is None:
                # displayed_rgba_pixels = image_converter.converted_to_normalized_uint8(self.image.array)
                # displayed_rgba_pixels = image_converter.converted_to_rgba(displayed_rgba_pixels)

                displayed_rgba_pixels = image_converter.converted_to_rgba(self.image_pixels)
            else:
                displayed_rgba_pixels = self.image.colored_premultiplied_array

            self._displayed_pixels_data = displayed_rgba_pixels.data
            displayed_qimage_format = QImage.Format_RGBA8888_Premultiplied if displayed_rgba_pixels.itemsize == 1 \
                else QImage.Format_RGBA64_Premultiplied
            self._displayed_qimage_cache = image_converter.numpy_rgba_image_to_qimage(
                displayed_rgba_pixels, displayed_qimage_format)

            # Scale image to take into account spatial attributes (spacings)
            spatial_width = self.image.spatial.spacing[1] * self._displayed_qimage_cache.width()
            spatial_height = self.image.spatial.spacing[0] * self._displayed_qimage_cache.height()
            self._displayed_qimage_cache = self._displayed_qimage_cache.scaled(
                spatial_width, spatial_height, mode=Qt.SmoothTransformation)
        return self._displayed_qimage_cache


class _LayeredDisplayedImage(QObject):
    def __init__(self, layered_image: LayeredImage = None):
        super().__init__()

        self._displayed_layers = [_DisplayedImageLayer(image_layer) for image_layer in layered_image.layers] \
            if layered_image is not None else []
        self._names_displayed_layers = \
            {displayed_layer.name: displayed_layer for displayed_layer in self._displayed_layers}

    @property
    def displayed_layers(self):
        return self._displayed_layers

    def displayed_layer(self, name: str) -> _DisplayedImageLayer:
        return self._names_displayed_layers.get(name)

    def add_displayed_layer(self, displayed_layer: _DisplayedImageLayer):
        self._displayed_layers.append(displayed_layer)
        self._names_displayed_layers[displayed_layer.name] = displayed_layer

    def add_displayed_layer_from_layer(self, image_layer: ImageLayer, visible: bool = True,
                                       opacity: float = DEFAULT_LAYER_OPACITY) -> _DisplayedImageLayer:
        displayed_layer = _DisplayedImageLayer(image_layer, visible, opacity)
        self.add_displayed_layer(displayed_layer)
        return displayed_layer


class _LayeredImageGraphicsObject(QGraphicsObject):
    active_displayed_layer_changed = Signal(QGraphicsObject, QGraphicsObject)

    def __init__(self, parent: QGraphicsItem = None):
        super().__init__(parent)

        self._layered_displayed_image = _LayeredDisplayedImage()
        self._active_displayed_layer = None

        self._bounding_rect = QRectF()

    @property
    def displayed_layers(self):
        return self._layered_displayed_image.displayed_layers

    def displayed_layer(self, name: str) -> _DisplayedImageLayer:
        return self._layered_displayed_image.displayed_layer(name)

    @property
    def active_displayed_layer(self):
        return self._active_displayed_layer

    # def add_layer(self, image: FlatImage = None, name: str = '',
    #               visible: bool = True, opacity: float = DEFAULT_LAYER_OPACITY) -> _ImageItemLayer:
    #     layer = _ImageItemLayer(image, name, visible, opacity)
    #     self.layers.append(layer)
    #     self.names_layers[name] = layer
    #     # Calling update() several times normally results in just one paintEvent() call.
    #     # See QWidget::update() documentation.
    #     layer.image_updated.connect(self._on_layer_image_updated)
    #     layer.visibility_updated.connect(self.update)
    #
    #     if len(self.layers) == 1:  # If was added first layer
    #         self.active_layer = layer
    #         self.active_layer_changed.emit(None, self.active_layer)
    #         self._update_bounding_rect()  # self.prepareGeometryChange() will call update() if this is necessary.
    #     else:
    #         self.update()
    #
    #     return layer

    def add_displayed_layer_from_layer(self, image_layer: ImageLayer, visible: bool = True,
                                       opacity: float = DEFAULT_LAYER_OPACITY) -> _DisplayedImageLayer:
        displayed_layer = self._layered_displayed_image.add_displayed_layer_from_layer(image_layer, visible, opacity)

        # Calling update() several times normally results in just one paintEvent() call.
        # See QWidget::update() documentation.
        displayed_layer.image_updated.connect(self._on_displayed_layer_image_updated)
        displayed_layer.visibility_updated.connect(self.update)

        if len(self.displayed_layers) == 1:  # If was added first layer
            self._active_displayed_layer = displayed_layer
            self.active_displayed_layer_changed.emit(None, self.active_displayed_layer)
            self._update_bounding_rect()  # self.prepareGeometryChange() will call update() if this is necessary.
        else:
            self.update()

        return displayed_layer

    def boundingRect(self):
        return self._bounding_rect

    def _update_bounding_rect(self):
        self.prepareGeometryChange()

        if self.displayed_layers:
            # TODO: images of layers can have different spatial bounding boxes.
            #  We have to use union of bounding boxes of every layer.
            #  Now we use only bounding box of first layer.
            first_layer_image = self._layered_displayed_image.displayed_layers[0].image
            rect_top_left_pixel_indexes = np.array([0, 0])
            rect_bottom_right_pixel_indexes = first_layer_image.array.shape[:2]
            rect_top_left_pos = first_layer_image.pixel_indexes_to_pos(rect_top_left_pixel_indexes)
            rect_bottom_right_pos = first_layer_image.pixel_indexes_to_pos(rect_bottom_right_pixel_indexes)
            self._bounding_rect = QRectF(QPointF(rect_top_left_pos[1], rect_top_left_pos[0]),
                                         QPointF(rect_bottom_right_pos[1], rect_bottom_right_pos[0]))

            # The method below does not take into account image origin (spatial attribute)
            # image = self.layers[0].displayed_image
            # image_rect = image.rect()
            # self._bounding_rect = QRectF(image_rect)  # item position will be in the top left point of image

            # Item position will be in the center of image
            # self._bounding_rect = QRectF(-image_rect.width() / 2, -image_rect.height() / 2,
            #                              image_rect.width(), image_rect.height())
        else:
            self._bounding_rect = QRectF()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for displayed_layer in self.displayed_layers:
            if displayed_layer.image is not None and displayed_layer.visible:
                painter.setOpacity(displayed_layer.opacity)
                image_origin = displayed_layer.image.spatial.origin
                painter.drawImage(QPointF(image_origin[1], image_origin[0]), displayed_layer.displayed_image)

    def _on_displayed_layer_image_updated(self, image: FlatImage):
        self.update()

    def print_layers(self):
        for index, layer in enumerate(self.displayed_layers):
            print(f'Layer {index}: {layer.name}')


class LayeredImageViewer(DataViewer):
    # before_image_changed = Signal()
    # image_changed = Signal()
    # colormap_active_class_changed = Signal(int)
    data_name_changed = Signal(str)

    def __init__(self, data: LayeredImage = None, zoomable: bool = True):
        super().__init__(data)

        print('FlatImageViewer __init__')

        self.layered_image_graphics_object = _LayeredImageGraphicsObject()
        self.layered_image_graphics_object.active_displayed_layer_changed.connect(
            self._on_active_displayed_layer_changed)

        self.graphics_scene = QGraphicsScene()
        self.graphics_scene.addItem(self.layered_image_graphics_object)

        self.graphics_view = GraphicsView(self.graphics_scene, zoomable)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.graphics_view)
        self.setLayout(grid_layout)

    def add_layer(self, layer: ImageLayer):
        self.data.add_layer(layer)

    def add_displayed_layer_from_layer(self, image_layer: ImageLayer, visible: bool = True,
                                       opacity: float = DEFAULT_LAYER_OPACITY) -> _DisplayedImageLayer:
        return self.layered_image_graphics_object.add_displayed_layer_from_layer(image_layer, visible, opacity)

    def displayed_layer(self, name: str) -> _DisplayedImageLayer:
        return self.layered_image_graphics_object.displayed_layer(name)

    @property
    def active_displayed_layer(self):
        return self.layered_image_graphics_object.active_displayed_layer

    @property
    def layers(self):
        return self.layered_image_graphics_object.layers

    @property
    def viewport(self):
        return self.graphics_view.viewport()

    def viewport_pos_to_image_pixel_indexes(self, viewport_pos: QPoint, image: Image) -> np.ndarray:
        layered_image_item_pos = self.viewport_pos_to_layered_image_item_pos(viewport_pos)
        return image.pos_to_pixel_indexes(np.array([layered_image_item_pos.y(), layered_image_item_pos.x()]))

    def viewport_pos_to_image_pixel_indexes_rounded(self, viewport_pos: QPoint, image: Image) -> np.ndarray:
        layered_image_item_pos = self.viewport_pos_to_layered_image_item_pos(viewport_pos)
        return image.pos_to_pixel_indexes_rounded(np.array([layered_image_item_pos.y(), layered_image_item_pos.x()]))

    def viewport_pos_to_layered_image_item_pos(self, viewport_pos: QPoint) -> QPointF:
        scene_pos = self.graphics_view.mapToScene(viewport_pos)
        return self.layered_image_graphics_object.mapFromScene(scene_pos)

    def pos_to_layered_image_item_pos(self, pos: QPoint) -> QPointF:
        # From viewer pos to |self.graphics_view| pos
        graphics_view_pos = self.graphics_view.mapFrom(self, pos)
        # From |self.graphics_view| pos to |self.viewport| pos
        viewport_pos = self.viewport.mapFrom(self.graphics_view, graphics_view_pos)
        return self.viewport_pos_to_layered_image_item_pos(viewport_pos)

    def center(self):
        print('center')
        self.graphics_view.centerOn(self.layered_image_graphics_object)

    def _on_active_displayed_layer_changed(self, old_active_layer: _ImageItemLayer, new_active_layer: _ImageItemLayer):
        if old_active_layer is not None:
            old_active_layer.image_updated.disconnect(self._on_active_layer_image_updated)
        if new_active_layer is not None:
            new_active_layer.image_updated.connect(self._on_active_layer_image_updated)

    def _on_active_layer_image_updated(self, image: FlatImage):
        self.data_name_changed.emit(image.path.name)

    def print_layers(self):
        self.layered_image_graphics_object.print_layers()
