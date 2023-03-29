from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QCursor, QPixmap, QAction
from PySide6.QtWidgets import QWidget, QDockWidget

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.tools.images import icons_rc  # noqa: F401
from bsmu.vision.plugins.windows.main import ToolsMenu
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.base import ImageLayerView

if TYPE_CHECKING:
    import numpy as np
    from PySide6.QtCore import QPoint, QPointF
    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.core.image.base import Image
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, ImageLayer
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
            tool_settings_widget_cls: Type[ViewerToolSettingsWidget],
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
        self._tool_settings_widget_cls = tool_settings_widget_cls
        self._action_name = action_name
        self._action_shortcut = action_shortcut

        self._mdi_viewer_tool: MdiViewerTool | None = None

        self._tool_action: QAction | None = None
        self._tool_temporary_deactivated: bool = False

    def _enable(self):
        if not self._action_name:
            return

        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        tool_settings = self._tool_settings_cls.from_config(self.config)
        self._mdi_viewer_tool = MdiViewerTool(
            self._main_window, self._mdi, self._tool_cls, tool_settings, self._tool_settings_widget_cls)

        self._tool_action = self._main_window.add_menu_action(
            ToolsMenu, self._action_name, self._tool_action_triggered, self._action_shortcut, checkable=True)

        self._main_window.add_menu_action(ToolsMenu, 'Uncheck Tool', self._deactivate_active_tool, Qt.Key_Escape)

        self._main_window.installEventFilter(self)

    def _disable(self):
        self._main_window.removeEventFilter(self)

        self._mdi_viewer_tool = None
        self._tool_action = None

        raise NotImplemented()

    def _tool_action_triggered(self, checked: bool):
        self._mdi_viewer_tool.activate() if checked else self._mdi_viewer_tool.deactivate()

    def _deactivate_active_tool(self):
        if self._tool_action.isChecked():
            self._tool_action.activate(QAction.Trigger)

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_1 and not event.isAutoRepeat():
            if self._tool_action.isChecked():
                self._tool_action.activate(QAction.Trigger)
                self._tool_temporary_deactivated = True
                return True
        elif event.type() == QEvent.KeyRelease and event.key() == Qt.Key_1 and not event.isAutoRepeat():
            if self._tool_temporary_deactivated and not self._tool_action.isChecked():
                self._tool_action.activate(QAction.Trigger)
                self._tool_temporary_deactivated = False
                return True
        return super().eventFilter(watched_obj, event)


class MdiViewerTool(QObject):
    def __init__(
            self,
            main_window: MainWindow,
            mdi: Mdi,
            tool_cls: Type[ViewerTool],
            tool_settings: ViewerToolSettings,
            tool_settings_widget_cls: Type[ViewerToolSettingsWidget]
    ):
        super().__init__()

        self._main_window = main_window
        self._mdi = mdi
        self._tool_csl = tool_cls
        self._tool_settings = tool_settings
        self._tool_settings_widget_cls = tool_settings_widget_cls
        self._tool_settings_widget = None
        self._tool_settings_dock_widget = None

        self._viewer_tool_by_sub_window = {}  # DataViewerSubWindow: ViewerTool

    def activate(self):
        if self._tool_settings_widget is None:
            self._tool_settings_widget = self._tool_settings_widget_cls(self._tool_settings)
            self._tool_settings_dock_widget = QDockWidget('Tool Settings', self._main_window)
            self._tool_settings_dock_widget.setWidget(self._tool_settings_widget)
            self._main_window.addDockWidget(Qt.LeftDockWidgetArea, self._tool_settings_dock_widget)

        for sub_window in self._mdi.subWindowList():
            viewer_tool = self._sub_window_viewer_tool(sub_window)
            if viewer_tool is not None:
                viewer_tool.activate()

    def deactivate(self):
        for viewer_tool in self._viewer_tool_by_sub_window.values():
            viewer_tool.deactivate()
        self._viewer_tool_by_sub_window.clear()

        self._main_window.removeDockWidget(self._tool_settings_dock_widget)
        self._tool_settings_dock_widget = None
        self._tool_settings_widget = None

    def _sub_window_viewer_tool(self, sub_window: DataViewerSubWindow):
        if not isinstance(sub_window, LayeredImageViewerSubWindow):
            return None

        viewer_tool = self._viewer_tool_by_sub_window.get(sub_window)
        if viewer_tool is None:
            viewer_tool = self._tool_csl(sub_window.viewer, self._tool_settings)
            self._viewer_tool_by_sub_window[sub_window] = viewer_tool
        return viewer_tool


class ViewerToolSettings(QObject):
    def __init__(self):
        super().__init__()

        self._cursor_file_name = ':/icons/brush.svg'  # TODO: Take this from config and pass as parameter
        self._cursor = None

    @property
    def cursor(self) -> QCursor:
        if self._cursor is None:
            cursor_icon = QPixmap(self._cursor_file_name, format=b'svg')
            self._cursor = QCursor(cursor_icon, hotX=0, hotY=0)
        return self._cursor

    @classmethod
    def from_config(cls, config: UnitedConfig) -> ViewerToolSettings:
        return cls()


class ViewerToolSettingsWidget(QWidget):
    def __init__(self, tool_settings: ViewerToolSettings, parent: QWidget = None):
        super().__init__(parent)

        self._tool_settings = tool_settings

    @property
    def tool_settings(self) -> ViewerToolSettings:
        return self._tool_settings


class ViewerTool(QObject):
    def __init__(self, viewer: DataViewer, settings: ViewerToolSettings):
        super().__init__()

        self.viewer = viewer
        self._settings = settings

    @property
    def settings(self) -> ViewerToolSettings:
        return self._settings

    def activate(self):
        self.viewer.viewport.setCursor(self._settings.cursor)
        self.viewer.viewport.installEventFilter(self)

    def deactivate(self):
        self.viewer.viewport.removeEventFilter(self)
        self.viewer.viewport.unsetCursor()


class LayeredImageViewerToolSettings(ViewerToolSettings):
    def __init__(self, layers_props: dict):
        super().__init__()

        self._layers_props = layers_props

        self._mask_palette = Palette.from_config(self._layers_props['mask'].get('palette'))
        self._tool_mask_palette = Palette.from_config(self._layers_props['tool_mask'].get('palette'))

    @property
    def layers_props(self) -> dict:
        return self._layers_props

    @property
    def mask_palette(self) -> Palette:
        return self._mask_palette

    @property
    def tool_mask_palette(self) -> Palette:
        return self._tool_mask_palette

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
            self, layer_key: str, name_property_key: str, image: Image, palette: Palette) -> ImageLayer:
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

    def deactivate(self):
        self.image_layer_view.image_layer.image_updated.disconnect(self._on_layer_image_updated)
        self.image_layer_view.image_view_updated.disconnect(self._on_layer_image_updated)

        self._remove_tool_mask_layer()

        super().deactivate()

    def _on_layer_image_updated(self):
        self.mask_layer = None

        mask_layer_props = self.layers_props['mask']
        if mask_layer_props.get('use_active_indexed_layer', True):
            active_layer = self.viewer.active_layer_view.image_layer
            if active_layer.is_indexed:
                self.mask_layer = active_layer
        if self.mask_layer is None and mask_layer_props.get('use_first_indexed_layer', True):
            for layer in self.viewer.layers:
                if layer.is_indexed:
                    self.mask_layer = layer
                    break
        if self.mask_layer is None:
            self.mask_layer = self.create_nonexistent_layer_with_zeros_mask(
                'mask', LAYER_NAME_PROPERTY_KEY, self.image_layer_view.image, self.settings.mask_palette)
        self.mask_layer.image_updated.connect(self._update_masks)

        self.tool_mask_layer = self.create_nonexistent_layer_with_zeros_mask(
            'tool_mask', LAYER_NAME_PROPERTY_KEY, self.image_layer_view.image, self.settings.tool_mask_palette)

        self._update_masks()

    def _remove_tool_mask_layer(self):
        self.viewer.remove_layer(self.tool_mask_layer)

    def _update_masks(self):
        if self.mask_layer.image is None:
            self.mask_layer.image = self.image_layer_view.image.zeros_mask(palette=self.mask_layer.palette)
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
