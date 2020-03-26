from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import MenuType
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.base import ImageLayerView
from bsmu.vision_core.image.base import FlatImage
from bsmu.vision_core.palette import Palette

if TYPE_CHECKING:
    from PySide2.QtCore import Qt


class ViewerToolPlugin(Plugin):
    def __init__(self, app: App, tool_cls: Type[ViewerTool], action_name: str = '', action_shortcut: Qt.Key = None):
        super().__init__(app)

        self.tool_cls = tool_cls
        self.action_name = action_name
        self.action_shortcut = action_shortcut

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        self.mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi

        self.mdi_tool = MdiViewerTool(self.mdi, self.tool_cls, self.config)

    def _enable(self):
        if not self.action_name:
            return

        self.main_window.add_menu_action(MenuType.TOOLS, self.action_name,
                                         self.mdi_tool.activate, self.action_shortcut)

    def _disable(self):
        raise NotImplemented()


class MdiViewerTool(QObject):
    def __init__(self, mdi: Mdi, tool_cls: Type[ViewerTool], config):
        super().__init__()

        self.mdi = mdi
        self.tool_csl = tool_cls
        self.config = config

        self.sub_windows_viewer_tools = {}  # DataViewerSubWindow: ViewerTool

    def activate(self):
        for sub_window in self.mdi.subWindowList():
            viewer_tool = self._sub_window_viwer_tool(sub_window)
            if viewer_tool is not None:
                viewer_tool.activate()

    def _sub_window_viwer_tool(self, sub_window: DataViewerSubWindow):
        if not isinstance(sub_window, LayeredImageViewerSubWindow):
            return None

        viewer_tool = self.sub_windows_viewer_tools.get(sub_window)
        if viewer_tool is None:
            viewer_tool = self.tool_csl(sub_window.viewer, self.config)
            self.sub_windows_viewer_tools[sub_window] = viewer_tool
        return viewer_tool


class ViewerTool(QObject):
    def __init__(self, viewer: DataViewer, config: UnitedConfig):
        super().__init__()

        self.viewer = viewer
        self.config = config

    def activate(self):
        self.viewer.viewport.installEventFilter(self)


class LayeredImageViewerTool(ViewerTool):
    def __init__(self, viewer: LayeredImageViewer, config: UnitedConfig):
        super().__init__(viewer, config)

        self.image = None
        self.mask = None
        self.tool_mask = None

        self.mask_palette = None
        self.tool_mask_palette = None

    def create_nonexistent_layer_with_zeros_mask(
            self, layers_properties, layer_key: str, name_property_key: str, palette: Palette) -> _ImageItemLayer:
        layer_properties = layers_properties[layer_key]
        layer_name = layer_properties[name_property_key]
        layer = self.viewer.layer(layer_name)

        if layer is None:
            # Create and add the layer
            layer_image = FlatImage.zeros_mask_like(self.image, palette=palette)
            layer_opacity = layer_properties.get('opacity', ImageLayerView.DEFAULT_LAYER_OPACITY)
            layer = self.viewer.add_layer(layer_image, layer_name, opacity=layer_opacity)

        return layer

    def activate(self):
        super().activate()

        layers_properties = self.config.value('layers')
        NAME_PROPERTY_KEY = 'name'

        image_layer_properties = layers_properties['image']
        if image_layer_properties == 'active_layer':
            image_layer = self.viewer.active_layer_view
        else:
            image_layer_name = image_layer_properties.get(NAME_PROPERTY_KEY)
            if image_layer_name is not None:
                image_layer = self.viewer.layer(image_layer_name)
            else:
                image_layer_number = image_layer_properties.get('number')
                if image_layer_number is not None:
                    image_layer = self.viewer.layers[image_layer_number]
                else:
                    assert False, f'Unknown image layer properties: {image_layer_properties}'
        self.image = image_layer and image_layer.image

        mask_layer = self.create_nonexistent_layer_with_zeros_mask(
            layers_properties, 'mask', NAME_PROPERTY_KEY, self.mask_palette)
        self.mask = mask_layer.image

        tool_mask_layer = self.create_nonexistent_layer_with_zeros_mask(
            layers_properties, 'tool_mask', NAME_PROPERTY_KEY, self.tool_mask_palette)
        self.tool_mask = tool_mask_layer.image

        self.viewer.print_layers()

    def pos_to_layered_image_item_pos(self, viewport_pos: QPoint) -> QPointF:
        return self.viewer.viewport_pos_to_layered_image_item_pos(viewport_pos)

    def pos_to_image_pixel_indexes(self, viewport_pos: QPoint, image: Image) -> np.ndarray:
        return self.viewer.viewport_pos_to_image_pixel_indexes(viewport_pos, image)

    def pos_to_image_pixel_indexes_rounded(self, viewport_pos: QPoint, image: Image) -> np.ndarray:
        return self.viewer.viewport_pos_to_image_pixel_indexes_rounded(viewport_pos, image)
