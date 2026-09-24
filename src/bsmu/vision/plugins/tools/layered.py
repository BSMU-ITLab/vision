from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QObject, QPointF

from bsmu.vision.core.layers import Layer, RasterLayer
from bsmu.vision.core.palette import Palette
from bsmu.vision.plugins.tools import ViewerToolSettings
from bsmu.vision.plugins.tools.graphics import GraphicsViewerTool
from bsmu.vision.widgets.viewers.layered import LayeredDataViewer

if TYPE_CHECKING:
    import numpy as np
    from PySide6.QtCore import QPoint

    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.core.data.raster import Raster
    from bsmu.vision.core.layers import VectorLayer
    from bsmu.vision.core.selection import SelectionManager
    from bsmu.vision.core.visibility import Visibility
    from bsmu.vision.plugins.palette.settings import PalettePackSettings
    from bsmu.vision.plugins.tools import CursorConfig
    from bsmu.vision.plugins.undo import UndoManager


LAYER_NAME_PROPERTY_KEY = 'name'


class LayeredDataViewerToolSettings(ViewerToolSettings):
    def __init__(
            self,
            layers_props: dict,
            palette_pack_settings: PalettePackSettings,
            cursor_config: CursorConfig | None = None,
            action_icon_file_name: str = '',
    ) -> None:
        super().__init__(palette_pack_settings, cursor_config, action_icon_file_name)

        self._layers_props = layers_props

        mask_config = self._layers_props.get('mask')
        self._mask_palette = (
            Palette.from_config(mask_config.get('palette')) if mask_config is not None else None
        )

        tool_mask_config = self._layers_props.get('tool_mask')
        self._tool_mask_palette = (
            Palette.from_config(tool_mask_config.get('palette')) if tool_mask_config is not None else None
        )

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

    # Override in subclasses to declare which components are needed
    _uses_image: bool = False
    _uses_mask: bool = False
    _uses_tool_mask: bool = False

    def __init__(
            self,
            viewer: LayeredDataViewer,
            undo_manager: UndoManager,
            settings: LayeredDataViewerToolSettings,
    ) -> None:
        super().__init__(viewer, undo_manager, settings)

        needs_image = self._uses_image or self._uses_mask or self._uses_tool_mask
        self._image_resolver: ImageLayerResolver | None = (
            ImageLayerResolver(viewer, settings) if needs_image else None
        )
        self._mask_manager: MaskManager | None = (
            MaskManager(viewer, settings, self._image_resolver, parent=self) if self._uses_mask else None
        )
        self._tool_mask_manager: ToolMaskManager | None = (
            ToolMaskManager(viewer, settings, self._image_resolver, parent=self) if self._uses_tool_mask else None
        )

        self._vector_layer: VectorLayer | None = None

    @property
    def settings(self) -> LayeredDataViewerToolSettings:
        return cast(LayeredDataViewerToolSettings, self._settings)

    @property
    def selection_manager(self) -> SelectionManager:
        return self.viewer.selection_manager

    @property
    def image_layer(self) -> RasterLayer | None:
        return self._image_resolver.image_layer if self._image_resolver is not None else None

    @property
    def image(self) -> Raster | None:
        return self._image_resolver.image if self._image_resolver is not None else None

    @property
    def mask(self) -> Raster | None:
        return self._mask_manager.mask if self._mask_manager is not None else None

    @property
    def tool_mask(self) -> Raster | None:
        return self._tool_mask_manager.mask if self._tool_mask_manager is not None else None

    @property
    def mask_layer(self) -> RasterLayer | None:
        return self._mask_manager.mask_layer if self._mask_manager is not None else None

    @property
    def tool_mask_layer(self) -> RasterLayer | None:
        return self._tool_mask_manager.mask_layer if self._tool_mask_manager is not None else None

    @property
    def vector_layer(self) -> VectorLayer | None:
        return self._vector_layer

    @property
    def mask_palette(self) -> Palette:
        return self.settings.mask_palette

    @property
    def layers_props(self) -> dict:
        return self.settings.layers_props

    def activate(self) -> None:
        self.viewer.disable_panning()

        super().activate()

        if self._image_resolver is not None:
            self._image_resolver.activate()
        if self._mask_manager is not None:
            self._mask_manager.activate()
        if self._tool_mask_manager is not None:
            self._tool_mask_manager.activate()

    def deactivate(self) -> None:
        if self._tool_mask_manager is not None:
            self._tool_mask_manager.deactivate()
        if self._mask_manager is not None:
            self._mask_manager.deactivate()
        if self._image_resolver is not None:
            self._image_resolver.deactivate()

        super().deactivate()

        self.viewer.enable_panning()

    def map_viewport_to_pixel_coords(self, viewport_pos: QPoint | QPointF, layer: RasterLayer) -> np.ndarray:
        if isinstance(viewport_pos, QPointF):
            viewport_pos = viewport_pos.toPoint()
        return self.viewer.map_viewport_to_pixel_coords(viewport_pos, layer)

    def map_viewport_to_pixel_indices(self, viewport_pos: QPoint, layer: RasterLayer) -> np.ndarray:
        return self.viewer.map_viewport_to_pixel_indices(viewport_pos, layer)

    def _get_or_create_vector_layer(self, name: str, visibility: Visibility | None = None) -> VectorLayer:
        return self.viewer.get_or_create_vector_layer(name, visibility)


class ImageLayerResolver:
    """Resolves the image layer from the viewer based on layers_props['image'] configuration."""

    def __init__(self, viewer: LayeredDataViewer, settings: LayeredDataViewerToolSettings) -> None:
        self._viewer = viewer
        self._settings = settings

        self._image_layer: RasterLayer | None = None

    @property
    def image_layer(self) -> RasterLayer | None:
        return self._image_layer

    @property
    def image(self) -> Raster | None:
        """Current 2D slice of the image (full raster for 2D data)."""
        if self._image_layer is None or self._image_layer.data is None:
            return None
        slice_number = self._viewer.slice_controller.slice_number
        return self._image_layer.data.slice_2d(slice_number)

    def activate(self) -> None:
        """Resolve the image layer from the viewer."""
        self._image_layer = self._resolve()

    def deactivate(self) -> None:
        """Release the image layer reference."""
        self._image_layer = None

    def _resolve(self) -> RasterLayer:
        image_layer_props = self._settings.layers_props['image']
        if image_layer_props == 'active_layer':
            layer = self._viewer.active_layer
        else:
            image_layer_name = image_layer_props.get(LAYER_NAME_PROPERTY_KEY)
            if image_layer_name is not None:
                layer = self._viewer.layer_by_name(image_layer_name)
            else:
                image_layer_number = image_layer_props.get('number')
                if image_layer_number is not None:
                    layer = self._viewer.layers[image_layer_number]
                else:
                    assert False, f'Unknown image layer properties: {image_layer_props}'

        assert isinstance(layer, RasterLayer), (
            f'Image layer must be a RasterLayer, got {type(layer).__name__}: {layer}'
        )
        return layer


class MaskManagerBase(QObject):
    """Manages a mask layer synced with the image layer.
    Subclasses define mask creation (_configure_mask_layer) and deactivation cleanup."""

    def __init__(
            self,
            viewer: LayeredDataViewer,
            settings: LayeredDataViewerToolSettings,
            image_resolver: ImageLayerResolver,
            parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._viewer = viewer
        self._settings = settings

        self._image_resolver = image_resolver
        self._mask_layer: RasterLayer | None = None

    @property
    def mask_layer(self) -> RasterLayer | None:
        return self._mask_layer

    @property
    def mask(self) -> Raster | None:
        if self._mask_layer is None or self._mask_layer.data is None:
            return None

        slice_number = self._viewer.slice_controller.slice_number
        return self._mask_layer.data.slice_2d(slice_number)

    @property
    def image_layer(self) -> RasterLayer | None:
        return self._image_resolver.image_layer

    @property
    def image(self) -> Raster | None:
        return self._image_resolver.image

    def activate(self) -> None:
        """Connect to model signals, set up mask layer.
        ImageLayerResolver must be activated before this."""
        image_layer = self.image_layer
        assert image_layer is not None, 'ImageLayerResolver must be activated before MaskManagerBase'
        image_layer.data_changed.connect(self._on_image_updated)
        image_layer.image_shape_changed.connect(self._on_image_updated)
        self._on_image_updated()

    def deactivate(self) -> None:
        """Disconnect signals, run subclass cleanup, release mask reference."""
        self._on_before_deactivate()
        self._set_mask_layer(None)
        image_layer = self.image_layer
        if image_layer is not None:
            image_layer.data_changed.disconnect(self._on_image_updated)
            image_layer.image_shape_changed.disconnect(self._on_image_updated)

    def _configure_mask_layer(self) -> RasterLayer:
        """Find or create the mask layer. Must be overridden."""
        raise NotImplementedError

    def _on_before_deactivate(self) -> None:
        """Called before deactivation. Override for cleanup (e.g., remove layer)."""
        pass

    def _on_image_updated(self) -> None:
        self._set_mask_layer(self._configure_mask_layer())
        self._update_mask()

    def _set_mask_layer(self, new_layer: RasterLayer | None) -> None:
        if self._mask_layer == new_layer:
            return

        if self._mask_layer is not None:
            self._mask_layer.data_changed.disconnect(self._update_mask)
        self._mask_layer = new_layer
        if self._mask_layer is not None:
            self._mask_layer.data_changed.connect(self._update_mask)

    def _create_layer_with_zeros_mask(self, layer_key: str, palette: Palette) -> RasterLayer:
        layer_props = self._settings.layers_props[layer_key]
        layer_name = layer_props[LAYER_NAME_PROPERTY_KEY]
        layer = self._viewer.layer_by_name(layer_name)
        if layer is None:
            layer_image = self.image_layer.data.zeros_mask(palette=palette)
            layer = self._viewer.add_layer_from_image(layer_image, layer_name)
            layer.opacity = layer_props.get('opacity', Layer.DEFAULT_OPACITY)
        return layer

    def _update_mask(self) -> None:
        if self._mask_layer.data is None:
            self._mask_layer.data = self.image_layer.data.zeros_mask(palette=self._mask_layer.palette)


class MaskManager(MaskManagerBase):
    """Permanent mask layer for user drawing. Survives tool deactivation."""

    def _configure_mask_layer(self) -> RasterLayer:
        mask_layer_props = self._settings.layers_props['mask']
        if mask_layer_props.get('use_active_indexed_layer', True):
            active_layer = self._viewer.active_layer
            if active_layer.is_indexed:
                return active_layer

        if mask_layer_props.get('use_first_indexed_layer', True):
            for layer in self._viewer.layers:
                if layer.is_indexed:
                    return layer

        return self._create_layer_with_zeros_mask('mask', self._settings.mask_palette)

    def _on_before_deactivate(self) -> None:
        pass  # Mask survives deactivation


class ToolMaskManager(MaskManagerBase):
    """Temporary tool mask (e.g., brush preview). Removed on deactivation."""

    def _configure_mask_layer(self) -> RasterLayer:
        return self._create_layer_with_zeros_mask('tool_mask', self._settings.tool_mask_palette)

    def _on_before_deactivate(self) -> None:
        self._remove_layer()

    def _remove_layer(self) -> None:
        if self._mask_layer is not None:
            self._viewer.remove_layer(self._mask_layer)
