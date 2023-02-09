from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import ToolsMenu
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.base import ImageLayerView

if TYPE_CHECKING:
    import numpy as np
    from PySide6.QtCore import Qt, QPoint, QPointF
    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.core.image.base import Image
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer
    from bsmu.vision.widgets.viewers.base import DataViewer
    from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow
    from typing import Type


LAYER_NAME_PROPERTY_KEY = 'name'


class ViewerToolPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            tool_cls: Type[ViewerTool],
            tool_settings_cls: Type[ViewerToolSettings],
            action_name: str = '',
            action_shortcut: Qt.Key = None,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._tool_cls = tool_cls
        self._tool_settings_cls = tool_settings_cls
        self._action_name = action_name
        self._action_shortcut = action_shortcut

        self._mdi_viewer_tool: MdiViewerTool | None = None

    def _enable(self):
        if not self._action_name:
            return

        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        tool_settings = self._tool_settings_cls.from_config(self.config)
        self._mdi_viewer_tool = MdiViewerTool(self._mdi, self._tool_cls, tool_settings)

        self._main_window.add_menu_action(
            ToolsMenu, self._action_name, self._mdi_viewer_tool.activate, self._action_shortcut)

    def _disable(self):
        self._mdi_viewer_tool = None

        raise NotImplemented()


class MdiViewerTool(QObject):
    def __init__(self, mdi: Mdi, tool_cls: Type[ViewerTool], tool_settings: ViewerToolSettings):
        super().__init__()

        self.mdi = mdi
        self.tool_csl = tool_cls
        self._tool_settings = tool_settings

        self._viewer_tool_by_sub_window = {}  # DataViewerSubWindow: ViewerTool

    def activate(self):
        for sub_window in self.mdi.subWindowList():
            viewer_tool = self._sub_window_viewer_tool(sub_window)
            if viewer_tool is not None:
                viewer_tool.activate()

    def _sub_window_viewer_tool(self, sub_window: DataViewerSubWindow):
        if not isinstance(sub_window, LayeredImageViewerSubWindow):
            return None

        viewer_tool = self._viewer_tool_by_sub_window.get(sub_window)
        if viewer_tool is None:
            viewer_tool = self.tool_csl(sub_window.viewer, self._tool_settings)
            self._viewer_tool_by_sub_window[sub_window] = viewer_tool
        return viewer_tool


class ViewerToolSettings(QObject):
    @classmethod
    def from_config(cls, config: UnitedConfig) -> ViewerToolSettings:
        return cls()


class ViewerTool(QObject):
    def __init__(self, viewer: DataViewer, settings: ViewerToolSettings):
        super().__init__()

        self.viewer = viewer
        self._settings = settings

    @property
    def settings(self) -> ViewerToolSettings:
        return self._settings

    def activate(self):
        self.viewer.viewport.installEventFilter(self)


class LayeredImageViewerToolSettings(ViewerToolSettings):
    def __init__(self, layers_props: dict):
        super().__init__()

        self._layers_props = layers_props

    @property
    def layers_props(self) -> dict:
        return self._layers_props

    @staticmethod
    def layers_props_from_config(config: UnitedConfig) -> dict:
        return config.value('layers')

    @classmethod
    def from_config(cls, config: UnitedConfig) -> LayeredImageViewerToolSettings:
        return cls(cls.layers_props_from_config(config))


class LayeredImageViewerTool(ViewerTool):
    def __init__(self, viewer: LayeredImageViewer, settings: LayeredImageViewerToolSettings):
        super().__init__(viewer, settings)

        self.image_layer_view = None
        self.mask_layer = None
        self.tool_mask_layer = None

        # self.image = None
        # self.mask = None
        # self.tool_mask = None

        self.mask_palette = None
        self.tool_mask_palette = None

    @property
    def image(self) -> FlatImage:
        return self.image_layer_view and self.image_layer_view.flat_image

    @property
    def mask(self) -> FlatImage:
        return self.viewer.layer_view_by_model(self.mask_layer).flat_image

    @property
    def tool_mask(self) -> FlatImage:
        return self.viewer.layer_view_by_model(self.tool_mask_layer).flat_image

    @property
    def layers_props(self) -> dict:
        return self.settings.layers_props

    def create_nonexistent_layer_with_zeros_mask(
            self, layer_key: str, name_property_key: str, image: Image, palette: Palette) -> _ImageItemLayer:
        layer_props = self.layers_props[layer_key]
        layer_name = layer_props[name_property_key]
        layer = self.viewer.layer_by_name(layer_name)

        if layer is None:
            # Create and add the layer
            layer_image = image.zeros_mask(palette=palette)
            layer = self.viewer.add_layer_from_image(layer_image, layer_name)

        layer_opacity = layer_props.get('opacity', ImageLayerView.DEFAULT_LAYER_OPACITY)
        self.viewer.layer_view_by_model(layer).opacity = layer_opacity

        return layer

    def activate(self):
        super().activate()

        image_layer_props = self.layers_props['image']
        if image_layer_props == 'active_layer':
            self.image_layer_view = self.viewer.active_layer_view
        else:
            image_layer_name = image_layer_props.get(LAYER_NAME_PROPERTY_KEY)
            if image_layer_name is not None:
                self.image_layer_view = self.viewer.layer_view_by_name(image_layer_name)
            else:
                image_layer_number = image_layer_props.get('number')
                if image_layer_number is not None:
                    self.image_layer_view = self.viewer.layer_views[image_layer_number]
                else:
                    assert False, f'Unknown image layer properties: {image_layer_props}'

        self.image_layer_view.image_layer.image_updated.connect(self._on_layer_image_updated)
        self.image_layer_view.image_view_updated.connect(self._on_layer_image_updated)

        self._on_layer_image_updated()

        self.viewer.print_layer_views()

    def _on_layer_image_updated(self):
        self.mask_layer = self.create_nonexistent_layer_with_zeros_mask(
            'mask', LAYER_NAME_PROPERTY_KEY, self.image_layer_view.image, self.mask_palette)
        self.mask_layer.image_updated.connect(self._update_masks)

        self.tool_mask_layer = self.create_nonexistent_layer_with_zeros_mask(
            'tool_mask', LAYER_NAME_PROPERTY_KEY, self.image_layer_view.image, self.tool_mask_palette)

        self._update_masks()

    def _update_masks(self):
        if self.mask_layer.image is None:
            self.mask_layer.image = self.image_layer_view.image.zeros_mask(palette=self.mask_palette)
            self.viewer.layer_view_by_model(self.mask_layer).slice_number = self.image_layer_view.slice_number

        self.tool_mask_layer.image = self.image_layer_view.image.zeros_mask(palette=self.tool_mask_layer.palette)
        self.viewer.layer_view_by_model(self.tool_mask_layer).slice_number = \
            self.viewer.layer_view_by_model(self.mask_layer).slice_number

    def pos_to_layered_image_item_pos(self, viewport_pos: QPoint) -> QPointF:
        return self.viewer.viewport_pos_to_layered_image_item_pos(viewport_pos)

    def pos_to_image_pixel_indexes(self, viewport_pos: QPoint, image: Image) -> np.ndarray:
        return self.viewer.viewport_pos_to_image_pixel_indexes(viewport_pos, image)

    def pos_f_to_image_pixel_indexes(self, viewport_pos_f: QPointF, image: Image) -> np.ndarray:
        return self.pos_to_image_pixel_indexes(viewport_pos_f.toPoint(), image)

    def pos_to_image_pixel_indexes_rounded(self, viewport_pos: QPoint, image: Image) -> np.ndarray:
        return self.viewer.viewport_pos_to_image_pixel_indexes_rounded(viewport_pos, image)
