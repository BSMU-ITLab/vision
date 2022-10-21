from __future__ import annotations

from typing import Protocol, runtime_checkable
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QImage
from PySide6.QtWidgets import QGridLayout, QGraphicsScene, QGraphicsObject, QGraphicsItem

import bsmu.vision.core.converters.image as image_converter
from bsmu.vision.core.image.base import Image, FlatImage
from bsmu.vision.core.image.layered import ImageLayer, LayeredImage
from bsmu.vision.core.models.base import positive_list_insert_index
from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision.widgets.viewers.graphics_view import GraphicsView

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget, QStyleOptionGraphicsItem

    from bsmu.vision.core.palette import Palette


class IntensityWindowing:
    def __init__(self, pixels: np.ndarray, window_width: float | None = None, window_level: float | None = None):
        self.pixels = pixels
        # Use explicit conversion from numpy type (e.g. np.uint8) to int, to prevent possible overflow
        pixels_min = int(pixels.min())
        pixels_max = int(pixels.max())
        self.window_width = window_width if window_width is not None else \
            pixels_max - pixels_min + 1
        self.window_level = window_level if window_level is not None else \
            (pixels_max + pixels_min + 1) / 2

    def windowing_applied(self) -> np.ndarray:
        #  https://github.com/dicompyler/dicompyler-core/blob/master/dicompylercore/dicomparser.py
        windowed_pixels = np.piecewise(
            self.pixels,
            [self.pixels <= (self.window_level - 0.5 - (self.window_width - 1) / 2),
             self.pixels > (self.window_level - 0.5 + (self.window_width - 1) / 2)],
            [0, 255, lambda pixels:
                ((pixels - (self.window_level - 0.5)) / (self.window_width - 1) + 0.5) * (255 - 0)])
        windowed_pixels = windowed_pixels.astype(np.uint8, copy=False)
        return windowed_pixels


class ImageLayerView(QObject):
    DEFAULT_LAYER_OPACITY = 1

    image_changed = Signal(Image)
    image_shape_changed = Signal(object, object)
    image_view_updated = Signal(FlatImage)
    visibility_changed = Signal(bool)
    opacity_changed = Signal(float)

    def __init__(self, image_layer: ImageLayer, visible: bool = True,
                 opacity: float = DEFAULT_LAYER_OPACITY):
        super().__init__()

        self._image_layer = image_layer
        self._image_layer.image_updated.connect(self._on_layer_image_updated)
        self._image_layer.image_shape_changed.connect(self.image_shape_changed)
        self._image_layer.image_pixels_modified.connect(self._update_image_view)
        self._visible = visible
        self._opacity = opacity

        self._image_view = None

        self._displayed_qimage_cache = None
        self._view_min_spacing = None
        # Store numpy array's data, because QImage uses it without copying,
        # and QImage will crash if it's data buffer will be deleted
        self._displayed_pixels_data = None

    @property
    def image_view(self) -> FlatImage:
        return self._image_view

    @property
    def image_layer(self) -> ImageLayer:
        return self._image_layer

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        if self._visible != value:
            self._visible = value
            self.visibility_changed.emit(self._visible)

    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float):
        if self._opacity != value:
            self._opacity = value
            self.opacity_changed.emit(self._opacity)

    @property
    def image(self) -> Image:
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
    def view_min_spacing(self) -> float:
        return self._view_min_spacing

    @view_min_spacing.setter
    def view_min_spacing(self, value: float):
        if self._view_min_spacing != value:
            self._view_min_spacing = value

            self._displayed_qimage_cache = None

    @property
    def displayed_image(self):
        if self._displayed_qimage_cache is None:
            if self.image_view.is_indexed:
                displayed_rgba_pixels = self.image_view.colored_premultiplied_array
            else:
                # displayed_rgba_pixels = image_converter.converted_to_normalized_uint8(self.image.array)
                # displayed_rgba_pixels = image_converter.converted_to_rgba(displayed_rgba_pixels)

                displayed_rgba_pixels = image_converter.converted_to_rgba(self.image_view.array)

            if not displayed_rgba_pixels.flags['C_CONTIGUOUS']:
                displayed_rgba_pixels = np.ascontiguousarray(displayed_rgba_pixels)
            self._displayed_pixels_data = displayed_rgba_pixels.data
            displayed_qimage_format = QImage.Format_RGBA8888_Premultiplied if displayed_rgba_pixels.itemsize == 1 \
                else QImage.Format_RGBA64_Premultiplied

            self._displayed_qimage_cache = image_converter.numpy_rgba_image_to_qimage(
                displayed_rgba_pixels, displayed_qimage_format)

            # Scale image to take into account spatial attributes (spacings)
            width_spacing = self.image_view.spatial.spacing[1]
            height_spacing = self.image_view.spatial.spacing[0]
            spatial_width = width_spacing / self.view_min_spacing * self._displayed_qimage_cache.width()
            spatial_height = height_spacing / self.view_min_spacing * self._displayed_qimage_cache.height()

            self._displayed_qimage_cache = self._displayed_qimage_cache.scaled(
                spatial_width, spatial_height, mode=Qt.SmoothTransformation)
        return self._displayed_qimage_cache

    def calculate_view_min_spacing(self) -> float:
        return float(self.image_view.spatial.spacing.min())  # cast to float, else it will have numpy.float type

    def _on_layer_image_updated(self, image: Image):
        self.image_changed.emit(image)
        self._update_image_view()

    def _update_image_view(self):
        self._displayed_qimage_cache = None
        self._image_view = self._create_image_view()
        if self._image_view is not None and self._image_view.n_channels == 1 and not self._image_view.is_indexed:
            self.intensity_windowing = IntensityWindowing(self._image_view.array)
            self._image_view.array = self.intensity_windowing.windowing_applied()
        self.image_view_updated.emit(self.image_view)


class _LayeredImageView(QObject):
    def __init__(self):
        super().__init__()

        self._layer_views = []
        self._names_layer_views = {}

        self._layers_views = {}  # {ImageLayer: ImageLayerView}

    @property
    def layer_views(self) -> list[ImageLayerView]:
        return self._layer_views

    def layer_view_by_name(self, name: str) -> ImageLayerView:
        return self._names_layer_views.get(name)

    def layer_view_by_model(self, image_layer: ImageLayer) -> ImageLayerView:
        return self._layers_views.get(image_layer)

    def add_layer_view(self, layer_view: ImageLayerView, layer_index: int):
        self._layer_views.insert(layer_index, layer_view)
        self._names_layer_views[layer_view.name] = layer_view
        self._layers_views[layer_view.image_layer] = layer_view

    def remove_layer_view(self, layer_view: ImageLayerView):
        del self._layers_views[layer_view.image_layer]
        del self._names_layer_views[layer_view.name]
        self._layer_views.remove(layer_view)


class _LayeredImageGraphicsObject(QGraphicsObject):
    layer_view_adding = Signal(ImageLayerView, int)
    layer_view_added = Signal(ImageLayerView, int)
    layer_view_removing = Signal(ImageLayerView, int)
    layer_view_removed = Signal(ImageLayerView, int)

    active_layer_view_changed = Signal(ImageLayerView, ImageLayerView)
    bounding_rect_changed = Signal(QRectF)

    def __init__(self, parent: QGraphicsItem = None):
        super().__init__(parent)

        self._layered_image_view = _LayeredImageView()
        self._active_layer_view = None

        self._bounding_rect_cache = None
        self._bounding_rect_cache_before_reset = None

        self._view_min_spacing: float = float('inf')

    @property
    def active_layer_view(self) -> ImageLayerView:
        return self._active_layer_view

    @active_layer_view.setter
    def active_layer_view(self, value: ImageLayerView):
        if self._active_layer_view != value:
            prev_active_layer_view = self._active_layer_view
            self._active_layer_view = value
            self.active_layer_view_changed.emit(prev_active_layer_view, self._active_layer_view)

    @property
    def layer_views(self) -> list[ImageLayerView]:
        return self._layered_image_view.layer_views

    @property
    def view_min_spacing(self) -> float:
        return self._view_min_spacing

    def layer_view_by_name(self, name: str) -> ImageLayerView:
        return self._layered_image_view.layer_view_by_name(name)

    def layer_view_by_model(self, image_layer: ImageLayer) -> ImageLayerView:
        return self._layered_image_view.layer_view_by_model(image_layer)

    def add_layer_view(self, layer_view: ImageLayerView, layer_index: int = None):
        layer_view_index = positive_list_insert_index(self.layer_views, layer_index)
        self.layer_view_adding.emit(layer_view, layer_view_index)

        self._layered_image_view.add_layer_view(layer_view, layer_view_index)

        # Calling update() several times normally results in just one paintEvent() call.
        # See QWidget::update() documentation.
        layer_view.image_changed.connect(self._on_layer_image_changed)
        layer_view.image_shape_changed.connect(self._on_layer_image_shape_changed)
        layer_view.image_view_updated.connect(self._on_layer_image_view_updated)
        layer_view.visibility_changed.connect(self._on_layer_view_visibility_changed)
        layer_view.opacity_changed.connect(self._on_layer_view_opacity_changed)

        if len(self.layer_views) == 1:  # If was added first layer view
            self.active_layer_view = layer_view

        self._update_view_min_spacing()

        self._reset_bounding_rect_cache()  # self.prepareGeometryChange() will call update() if this is necessary.

        self.layer_view_added.emit(layer_view, layer_view_index)

    def remove_layer_view(self, layer_view: ImageLayerView):
        layer_index = self.layer_views.index(layer_view)
        self.layer_view_removing.emit(layer_view, layer_index)

        self._layered_image_view.remove_layer_view(layer_view)

        layer_view.image_changed.disconnect(self._on_layer_image_changed)
        layer_view.image_shape_changed.disconnect(self._on_layer_image_shape_changed)
        layer_view.image_view_updated.disconnect(self._on_layer_image_view_updated)
        layer_view.visibility_changed.disconnect(self._on_layer_view_visibility_changed)
        layer_view.opacity_changed.disconnect(self._on_layer_view_opacity_changed)

        if len(self.layer_views) == 0:
            self.active_layer_view = None

        self._update_view_min_spacing()

        self._reset_bounding_rect_cache()  # self.prepareGeometryChange() will call update() if this is necessary.

        self.layer_view_removed.emit(layer_view, layer_index)

    def remove_layer_view_by_model(self, image_layer):
        self.remove_layer_view(self._layered_image_view.layer_view_by_model(image_layer))

    def boundingRect(self):
        if self._bounding_rect_cache is None:
            self._bounding_rect_cache = self._calculate_bounding_rect()
            if self._bounding_rect_cache != self._bounding_rect_cache_before_reset:
                self.bounding_rect_changed.emit(self._bounding_rect_cache)
        return self._bounding_rect_cache

    def _calculate_bounding_rect(self) -> QRectF:
        if self.layer_views:
            # TODO: images of layers can have different spatial bounding boxes.
            #  We have to use union of bounding boxes of every layer.
            #  Now we use only bounding box of first layer.
            first_layer_image_view = self.layer_views[0].image_view
            if first_layer_image_view is None:
                return QRectF()

            rect_top_left_pixel_indexes = np.array([0, 0])
            rect_bottom_right_pixel_indexes = np.array(first_layer_image_view.array.shape[:2])

            rect_top_left_pos = first_layer_image_view.pixel_indexes_to_pos(
                rect_top_left_pixel_indexes / self.view_min_spacing)
            rect_bottom_right_pos = first_layer_image_view.pixel_indexes_to_pos(
                rect_bottom_right_pixel_indexes / self.view_min_spacing)

            bounding_rect = QRectF(QPointF(rect_top_left_pos[1], rect_top_left_pos[0]),
                                   QPointF(rect_bottom_right_pos[1], rect_bottom_right_pos[0]))

            # The method below does not take into account image origin (spatial attribute)
            # image = self.layer_views[0].displayed_image
            # image_rect = image.rect()
            # self._bounding_rect = QRectF(image_rect)  # item position will be in the top left point of image

            # Item position will be in the center of image
            # self._bounding_rect = QRectF(-image_rect.width() / 2, -image_rect.height() / 2,
            #                              image_rect.width(), image_rect.height())
        else:
            bounding_rect = QRectF()

        return bounding_rect

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        # painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for layer_view in self.layer_views:
            if layer_view.visible and layer_view.image_view is not None:
                painter.setOpacity(layer_view.opacity)
                image_view_origin = layer_view.image_view.spatial.origin
                painter.drawImage(QPointF(image_view_origin[1], image_view_origin[0]), layer_view.displayed_image)

    def _on_layer_image_changed(self, image: Image):
        self._reset_bounding_rect_cache()

    def _on_layer_image_shape_changed(self, old_shape: tuple[int] | None, new_shape: tuple[int] | None):
        self._reset_bounding_rect_cache()

    def _reset_bounding_rect_cache(self):
        if self._bounding_rect_cache is not None:
            self.prepareGeometryChange()
            self._bounding_rect_cache_before_reset = self._bounding_rect_cache
            self._bounding_rect_cache = None

    def _update_view_min_spacing(self):
        calculated_view_min_spacing = float('inf')
        for layer_view in self.layer_views:
            if layer_view.image_view is None:
                continue

            layer_view_min_spacing = layer_view.calculate_view_min_spacing()
            if layer_view_min_spacing < calculated_view_min_spacing:
                calculated_view_min_spacing = layer_view_min_spacing

        self._view_min_spacing = calculated_view_min_spacing

        # Apply for all layers the same minimal view spacing to overlay them correctly
        for layer_view in self.layer_views:
            layer_view.view_min_spacing = self._view_min_spacing

    def _on_layer_image_view_updated(self, image_view: FlatImage):
        self._update_view_min_spacing()

        self.update()

    def _on_layer_view_visibility_changed(self, visible: bool):
        self.update()

    def _on_layer_view_opacity_changed(self, opacity: float):
        self.update()


class LayeredImageViewer(DataViewer):
    layer_view_adding = Signal(ImageLayerView, int)
    layer_view_added = Signal(ImageLayerView, int)
    layer_view_removing = Signal(ImageLayerView, int)
    layer_view_removed = Signal(ImageLayerView, int)

    data_name_changed = Signal(str)

    def __init__(self, data: LayeredImage = None, zoomable: bool = True):
        super().__init__()  # do not pass |data| as parameter, cause we need at first create _LayeredImageGraphicsObject
        # Thus, |data| is assigned later, when _LayeredImageGraphicsObject will be created

        self.layered_image_graphics_object = _LayeredImageGraphicsObject()
        self.layered_image_graphics_object.active_layer_view_changed.connect(
            self._on_active_layer_view_changed)
        self.layered_image_graphics_object.bounding_rect_changed.connect(
            self._on_graphics_object_bounding_rect_changed)
        # self.layered_image_graphics_object.bounding_rect_changed.connect(
        #     self.graphics_scene.setSceneRect)
        self.layered_image_graphics_object.layer_view_adding.connect(self.layer_view_adding)
        self.layered_image_graphics_object.layer_view_added.connect(self.layer_view_added)
        self.layered_image_graphics_object.layer_view_removing.connect(self.layer_view_removing)
        self.layered_image_graphics_object.layer_view_removed.connect(self.layer_view_removed)

        self.data = data

        self.graphics_scene = QGraphicsScene()
        self.graphics_view = GraphicsView(self.graphics_scene, zoomable)

        self.graphics_scene.addItem(self.layered_image_graphics_object)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.graphics_view)
        self.setLayout(grid_layout)

    @property
    def active_layer_view(self) -> ImageLayerView:
        return self.layered_image_graphics_object.active_layer_view

    @property
    def active_layer(self) -> ImageLayer:
        return self.active_layer_view.image_layer

    @property
    def layers(self):
        return self.data.layers

    @property
    def layer_views(self) -> list[ImageLayerView]:
        return self.layered_image_graphics_object.layer_views

    def layer_view_by_name(self, name: str) -> ImageLayerView:
        return self.layered_image_graphics_object.layer_view_by_name(name)

    def layer_view_by_model(self, image_layer: ImageLayer) -> ImageLayerView:
        return self.layered_image_graphics_object.layer_view_by_model(image_layer)

    def layer_by_name(self, name: str) -> ImageLayer:
        return self.data.layer_by_name(name)

    def add_layer(self, layer: ImageLayer):
        self.data.add_layer(layer)

    def add_layer_from_image(self, image: Image, name: str = ''):
        layer = ImageLayer(image, name)
        self.add_layer(layer)
        return layer

    def add_graphics_item(self, item: QGraphicsItem):
        self.graphics_scene.addItem(item)

    def remove_graphics_item(self, item: QGraphicsItem):
        self.graphics_scene.removeItem(item)

    def _on_data_changing(self):
        if self.data is None:
            return

        self.data.layer_added.disconnect(self._add_layer_view_from_model)

        for layer in self.layers:
            self._remove_layer_view_by_model(layer)

    def _on_data_changed(self):
        if self.data is None:
            return

        self.data.layer_added.connect(self._add_layer_view_from_model)

        for layer in self.layers:
            self._add_layer_view_from_model(layer)

    def _add_layer_view(self, layer_view: ImageLayerView, layer_index: int = None):
        self.layered_image_graphics_object.add_layer_view(layer_view, layer_index)

    def _add_layer_view_from_model(self, image_layer: ImageLayer, layer_index: int = None) -> ImageLayerView:
        pass

    def _remove_layer_view_by_model(self, image_layer: ImageLayer):
        self.layered_image_graphics_object.remove_layer_view_by_model(image_layer)

    @property
    def viewport(self):
        return self.graphics_view.viewport()

    def viewport_pos_to_image_pixel_indexes(self, viewport_pos: QPoint, image: Image) -> np.ndarray:
        layered_image_item_pos = self.viewport_pos_to_layered_image_item_pos(viewport_pos)
        return image.pos_to_pixel_indexes(np.array([layered_image_item_pos.y(), layered_image_item_pos.x()])) \
            * self.layered_image_graphics_object.view_min_spacing

    def viewport_pos_to_image_pixel_indexes_rounded(self, viewport_pos: QPoint, image: Image) -> np.ndarray:
        return self.viewport_pos_to_image_pixel_indexes(viewport_pos, image).round().astype(np.int_)

    def viewport_pos_to_layered_image_item_pos(self, viewport_pos: QPoint) -> QPointF:
        scene_pos = self.graphics_view.mapToScene(viewport_pos)
        return self.layered_image_graphics_object.mapFromScene(scene_pos)

    def pos_to_layered_image_item_pos(self, pos: QPoint) -> QPointF:
        # From viewer pos to |self.graphics_view| pos
        graphics_view_pos = self.graphics_view.mapFrom(self, pos)
        # From |self.graphics_view| pos to |self.viewport| pos
        viewport_pos = self.viewport.mapFrom(self.graphics_view, graphics_view_pos)
        return self.viewport_pos_to_layered_image_item_pos(viewport_pos)

    def fit_image_in(self):
        self.graphics_view.fit_in_view(self.layered_image_graphics_object.boundingRect(), Qt.KeepAspectRatio)

    def _on_active_layer_view_changed(self, old_active_layer_view: ImageLayerView,
                                      new_active_layer_view: ImageLayerView):
        if old_active_layer_view is not None:
            old_active_layer_view.image_view_updated.disconnect(self._on_active_layer_image_view_updated)
        if new_active_layer_view is not None:
            new_active_layer_view.image_view_updated.connect(self._on_active_layer_image_view_updated)

    def _on_graphics_object_bounding_rect_changed(self, rect: QRectF):
        self.graphics_view.set_visualized_scene_rect(rect)

    def _on_active_layer_image_view_updated(self, image_view: FlatImage):
        self.data_name_changed.emit('' if image_view is None else image_view.path_name)

    def print_layers(self):
        self.data.print_layers()

    def print_layer_views(self):
        for index, layer_view in enumerate(self.layer_views):
            print(f'Layer {index}: {layer_view.name} opacity={layer_view.opacity}')


@runtime_checkable
class LayeredImageViewerHolder(Protocol):
    @property
    def layered_image_viewer(self) -> LayeredImageViewer:
        pass
