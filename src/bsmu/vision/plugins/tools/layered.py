from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QPointF

from bsmu.vision.core.layers import Layer, VectorLayer
from bsmu.vision.core.palette import Palette
from bsmu.vision.plugins.tools import CursorConfig, ViewerToolSettings
from bsmu.vision.plugins.tools.graphics import GraphicsViewerTool
from bsmu.vision.widgets.viewers.layered import LayeredDataViewer

if TYPE_CHECKING:
    import numpy as np
    from PySide6.QtCore import QPoint

    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.core.data.raster import Raster
    from bsmu.vision.core.layers import RasterLayer
    from bsmu.vision.core.visibility import Visibility
    from bsmu.vision.plugins.palette.settings import PalettePackSettings
    from bsmu.vision.plugins.undo import UndoManager


LAYER_NAME_PROPERTY_KEY = 'name'


class LayeredDataViewerToolSettings(ViewerToolSettings):
    def __init__(
            self,
            layers_props: dict,
            palette_pack_settings: PalettePackSettings,
            cursor_config: CursorConfig = CursorConfig(),
            action_icon_file_name: str = '',
    ):
        super().__init__(palette_pack_settings, cursor_config, action_icon_file_name)

        self._layers_props = layers_props

        self._mask_palette = Palette.from_config(self._layers_props['mask'].get('palette'))
        self._tool_mask_palette = Palette.from_config(self._layers_props['tool_mask'].get('palette'))

    @property
    def layers_props(self) -> dict:
        return self._layers_props

    @property
    def mask_palette(self) -> Palette:
        return self._mask_palette or self.palette_pack_settings.main_palette

    @property
    def tool_mask_palette(self) -> Palette:
        return self._tool_mask_palette

    @property
    def vector_layer_name(self) -> str:
        DEFAULT_VECTOR_LAYER_NAME = 'vectors'
        vector_layer_config = self._layers_props.get('vector')
        if vector_layer_config is not None:
            return vector_layer_config.get('name', DEFAULT_VECTOR_LAYER_NAME)
        return DEFAULT_VECTOR_LAYER_NAME

    @staticmethod
    def layers_props_from_config(config: UnitedConfig) -> dict:
        return config.value('layers')

    @classmethod
    def from_config(
            cls, config: UnitedConfig, palette_pack_settings: PalettePackSettings) -> LayeredDataViewerToolSettings:
        return cls(cls.layers_props_from_config(config), palette_pack_settings)


class LayeredDataViewerTool(GraphicsViewerTool[LayeredDataViewer]):
    viewer_type: type[LayeredDataViewer] = LayeredDataViewer

    def __init__(
            self,
            viewer: LayeredDataViewer,
            undo_manager: UndoManager,
            settings: LayeredDataViewerToolSettings,
    ):
        super().__init__(viewer, undo_manager, settings)

        self.image_layer_view = None

        self._mask_layer: RasterLayer | None = None
        self._tool_mask_layer: RasterLayer | None = None
        self._vector_layer: VectorLayer | None = None

    @property
    def settings(self) -> LayeredDataViewerToolSettings:
        return cast(LayeredDataViewerToolSettings, self._settings)

    @property
    def image(self) -> Raster | None:
        return self.image_layer_view and self.image_layer_view.current_slice

    @property
    def mask(self) -> Raster | None:
        return self.viewer.actor_by_layer(self._mask_layer).current_slice

    @property
    def tool_mask(self) -> Raster | None:
        return self.viewer.actor_by_layer(self._tool_mask_layer).current_slice

    @property
    def mask_layer(self) -> RasterLayer:
        return self._mask_layer

    @property
    def tool_mask_layer(self) -> RasterLayer:
        return self._tool_mask_layer

    @property
    def vector_layer(self) -> VectorLayer | None:
        return self._vector_layer

    @property
    def mask_palette(self) -> Palette:
        return self.settings.mask_palette

    @property
    def layers_props(self) -> dict:
        return self.settings.layers_props

    def activate(self):
        self.viewer.disable_panning()

        super().activate()

        image_layer_props = self.layers_props['image']
        if image_layer_props == 'active_layer':
            self.image_layer_view = self.viewer.active_layer_actor
        else:
            image_layer_name = image_layer_props.get(LAYER_NAME_PROPERTY_KEY)
            if image_layer_name is not None:
                self.image_layer_view = self.viewer.actor_by_name(image_layer_name)
            else:
                image_layer_number = image_layer_props.get('number')
                if image_layer_number is not None:
                    self.image_layer_view = self.viewer.layer_actors[image_layer_number]
                else:
                    assert False, f'Unknown image layer properties: {image_layer_props}'

        self.image_layer_view.layer.data_changed.connect(self._on_layer_image_updated)
        self.image_layer_view.image_view_updated.connect(self._on_layer_image_updated)

        self._on_layer_image_updated()

    def deactivate(self):
        self._remove_tool_mask_layer()
        self._set_mask_layer(None)

        self.image_layer_view.layer.data_changed.disconnect(self._on_layer_image_updated)
        self.image_layer_view.image_view_updated.disconnect(self._on_layer_image_updated)
        self.image_layer_view = None

        super().deactivate()

        self.viewer.enable_panning()

    def _set_mask_layer(self, new_mask_layer: RasterLayer | None):
        if self._mask_layer == new_mask_layer:
            return

        if self._mask_layer is not None:
            self._mask_layer.data_changed.disconnect(self._update_masks)

        self._mask_layer = new_mask_layer

        if self._mask_layer is not None:
            self._mask_layer.data_changed.connect(self._update_masks)

    def _set_tool_mask_layer(self, new_tool_mask_layer: RasterLayer | None):
        if self._tool_mask_layer == new_tool_mask_layer:
            return

        if self._tool_mask_layer is not None:
            self._tool_mask_layer.data_changed.disconnect(self._update_tool_mask)

        self._tool_mask_layer = new_tool_mask_layer

        if self._tool_mask_layer is not None:
            self._tool_mask_layer.data_changed.connect(self._update_tool_mask)

    def _create_nonexistent_layer_with_zeros_mask(
            self, layer_key: str, name_property_key: str, image: Raster, palette: Palette) -> RasterLayer:
        layer_props = self.layers_props[layer_key]
        layer_name = layer_props[name_property_key]
        layer = self.viewer.layer_by_name(layer_name)

        if layer is None:
            # Create and add the layer
            layer_image = image.zeros_mask(palette=palette)
            layer = self.viewer.add_layer_from_image(layer_image, layer_name)
            layer.opacity = layer_props.get('opacity', Layer.DEFAULT_OPACITY)

        return layer

    def _on_layer_image_updated(self):
        self._set_mask_layer(self._configured_mask_layer())

        if self._tool_mask_layer is None:
            tool_mask_layer = self._create_nonexistent_layer_with_zeros_mask(
                'tool_mask', LAYER_NAME_PROPERTY_KEY, self.image_layer_view.raster, self.settings.tool_mask_palette)
            self._set_tool_mask_layer(tool_mask_layer)

        self._update_masks()

    def _configured_mask_layer(self) -> RasterLayer:
        mask_layer_props = self.layers_props['mask']
        if mask_layer_props.get('use_active_indexed_layer', True):
            active_layer = self.viewer.active_layer_actor.layer
            if active_layer.is_indexed:
                return active_layer

        if mask_layer_props.get('use_first_indexed_layer', True):
            for layer in self.viewer.layers:
                if layer.is_indexed:
                    return layer

        return self._create_nonexistent_layer_with_zeros_mask(
            'mask', LAYER_NAME_PROPERTY_KEY, self.image_layer_view.raster, self.mask_palette)

    def _remove_tool_mask_layer(self):
        if self._tool_mask_layer is not None:
            self.viewer.remove_layer(self._tool_mask_layer)
            self._set_tool_mask_layer(None)

    def _update_masks(self):
        if self._mask_layer.data is None:
            self._mask_layer.data = self.image_layer_view.raster.zeros_mask(palette=self._mask_layer.palette)
            self.viewer.actor_by_layer(self._mask_layer).slice_number = self.image_layer_view.slice_number

        self._update_tool_mask()

    def _update_tool_mask(self):
        if self._tool_mask_layer.data is None:
            self._tool_mask_layer.data = self.image_layer_view.raster.zeros_mask(palette=self._tool_mask_layer.palette)
            self.viewer.actor_by_layer(self._tool_mask_layer).slice_number = (
                self.viewer.actor_by_layer(self._mask_layer).slice_number)

    def map_viewport_to_pixel_coords(self, viewport_pos: QPoint | QPointF, layer: RasterLayer) -> np.ndarray:
        if isinstance(viewport_pos, QPointF):
            viewport_pos = viewport_pos.toPoint()
        return self.viewer.map_viewport_to_pixel_coords(viewport_pos, layer)

    def map_viewport_to_pixel_indices(self, viewport_pos: QPoint, layer: RasterLayer) -> np.ndarray:
        return self.viewer.map_viewport_to_pixel_indices(viewport_pos, layer)

    def _get_or_create_vector_layer(self, name: str, visibility: Visibility | None = None) -> VectorLayer:
        return self.viewer.get_or_create_vector_layer(name, visibility)
