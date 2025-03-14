from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from PySide6.QtCore import Qt, QEvent, QObject, Signal
from PySide6.QtGui import QCursor, QPixmap, QAction, QIcon
from PySide6.QtWidgets import QWidget, QDockWidget

from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins import Plugin
from bsmu.vision.plugins.tools.images import icons_rc  # noqa: F401
from bsmu.vision.plugins.windows.main import ToolsMenu
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered import ImageLayerView

if TYPE_CHECKING:
    import numpy as np
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtWidgets import QMdiSubWindow

    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.core.image import Image, FlatImage
    from bsmu.vision.core.image.layered import ImageLayer
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin, PalettePackSettings
    from bsmu.vision.plugins.undo import UndoPlugin, UndoManager
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.widgets.mdi.windows.data import DataViewerSubWindow
    from bsmu.vision.widgets.viewers.data import DataViewer
    from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer


LAYER_NAME_PROPERTY_KEY = 'name'


class ViewerToolPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'undo_plugin': 'bsmu.vision.plugins.undo.UndoPlugin',
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: type[ViewerTool],
            tool_settings_cls: type[ViewerToolSettings],
            tool_settings_widget_cls: type[ViewerToolSettingsWidget] = None,
            action_name: str = '',
            action_shortcut: Qt.Key = None,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._undo_plugin = undo_plugin
        self._undo_manager: UndoManager

        self._palette_pack_settings_plugin = palette_pack_settings_plugin
        self._palette_pack_settings: PalettePackSettings | None = None

        self._tool_cls = tool_cls
        self._tool_settings_cls = tool_settings_cls
        self._tool_settings_widget_cls = tool_settings_widget_cls
        self._action_name = action_name
        self._action_shortcut = action_shortcut

        self._mdi_viewer_tool: MdiViewerTool | None = None

        self._tool_action: QAction | None = None

    @property
    def mdi_viewer_tool(self) -> MdiViewerTool | None:
        return self._mdi_viewer_tool

    @property
    def tool_action(self) -> QAction | None:
        return self._tool_action

    @property
    def action_shortcut(self) -> Qt.Key | None:
        return self._action_shortcut

    def _enable(self):
        if not self._action_name:
            return

        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi
        self._undo_manager = self._undo_plugin.undo_manager
        self._palette_pack_settings = self._palette_pack_settings_plugin.settings

        tool_settings = self._tool_settings_cls.from_config(self.config, self._palette_pack_settings)
        self._mdi_viewer_tool = MdiViewerTool(
            self._main_window,
            self._mdi,
            self._undo_manager,
            self._tool_cls,
            tool_settings,
            self._tool_settings_widget_cls,
        )

        self._tool_action = self._main_window.add_menu_action(
            ToolsMenu, self._action_name, self._tool_action_triggered, self._action_shortcut, checkable=True)
        self._tool_action.setData(self._mdi_viewer_tool)
        self._tool_action.setAutoRepeat(False)
        self._tool_action.setIcon(QIcon(tool_settings.icon_file_name))

        self._mdi_viewer_tool.activation_changed.connect(self._on_mdi_viewer_tool_activation_changed)

    def _disable(self):
        self._mdi_viewer_tool.activation_changed.disconnect(self._on_mdi_viewer_tool_activation_changed)
        self._mdi_viewer_tool.cleanup()
        self._mdi_viewer_tool = None
        self._tool_action = None

        self._main_window = None
        self._mdi = None
        self._undo_manager = None
        self._palette_pack_settings = None

        raise NotImplementedError

    def _tool_action_triggered(self, checked: bool):
        self._mdi_viewer_tool.activate() if checked else self._mdi_viewer_tool.deactivate()

    def _on_mdi_viewer_tool_activation_changed(self, is_mdi_viewer_tool_active: bool):
        self._tool_action.setChecked(is_mdi_viewer_tool_active)


class MdiViewerTool(QObject):
    activating = Signal(QObject)  # MdiViewerTool is not defined yet, so use QObject
    activated = Signal(QObject)
    deactivating = Signal(QObject)
    deactivated = Signal(QObject)

    activation_changed = Signal(bool)

    def __init__(
            self,
            main_window: MainWindow,
            mdi: Mdi,
            undo_manager: UndoManager,
            tool_cls: type[ViewerTool],
            tool_settings: ViewerToolSettings,
            tool_settings_widget_cls: type[ViewerToolSettingsWidget],
    ):
        super().__init__()

        self._main_window = main_window
        self._mdi = mdi
        self._undo_manager = undo_manager
        self._tool_csl = tool_cls
        self._tool_settings = tool_settings
        self._tool_settings_widget_cls = tool_settings_widget_cls
        self._tool_settings_widget = None
        self._tool_settings_dock_widget = None

        self._viewer_tool_by_sub_window: dict[DataViewerSubWindow, ViewerTool] = {}

        self._is_active = False
        self._is_activating = False
        self._is_deactivating = False

        self._mdi.sub_window_added.connect(self._on_sub_window_added)

    def cleanup(self):
        self._mdi.sub_window_added.disconnect(self._on_sub_window_added)

    @property
    def is_active(self) -> bool:
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool):
        if self._is_active != value:
            self._is_active = value
            self.activation_changed.emit(self._is_active)

    def activate(self):
        if self._is_active or self._is_activating:
            return

        self._is_activating = True
        self.activating.emit(self)

        if self._tool_settings_widget is None and self._tool_settings_widget_cls is not None:
            self._tool_settings_widget = self._tool_settings_widget_cls(self._tool_settings)
            self._tool_settings_dock_widget = QDockWidget(self.tr('Tool Settings'), self._main_window)
            self._tool_settings_dock_widget.setWidget(self._tool_settings_widget)
            self._main_window.addDockWidget(Qt.LeftDockWidgetArea, self._tool_settings_dock_widget)

        for sub_window in self._mdi.subWindowList():
            self._activate_on_subwindow(sub_window)

        self.is_active = True
        self.activated.emit(self)
        self._is_activating = False

    def deactivate(self):
        if not self._is_active or self._is_deactivating:
            return

        self._is_deactivating = True
        self.deactivating.emit(self)

        for viewer_tool in self._viewer_tool_by_sub_window.values():
            viewer_tool.deactivate()
        self._viewer_tool_by_sub_window.clear()

        self._main_window.removeDockWidget(self._tool_settings_dock_widget)
        self._tool_settings_dock_widget = None
        self._tool_settings_widget = None

        self.is_active = False
        self.deactivated.emit(self)
        self._is_deactivating = False

    def _on_sub_window_added(self, sub_window: QMdiSubWindow):
        if self._is_active:
            self._activate_on_subwindow(sub_window)

    def _activate_on_subwindow(self, sub_window: QMdiSubWindow):
        viewer_tool = self._sub_window_viewer_tool(sub_window)
        if viewer_tool is not None:
            viewer_tool.activate()

    def _sub_window_viewer_tool(self, sub_window: DataViewerSubWindow):
        if not isinstance(sub_window, LayeredImageViewerSubWindow):
            return None

        viewer_tool = self._viewer_tool_by_sub_window.get(sub_window)
        if viewer_tool is None:
            viewer_tool = self._tool_csl(sub_window.viewer, self._undo_manager, self._tool_settings)
            self._viewer_tool_by_sub_window[sub_window] = viewer_tool
        return viewer_tool


class ViewerToolSettings(QObject):
    def __init__(self, palette_pack_settings: PalettePackSettings, icon_file_name: str = ''):
        super().__init__()

        self._palette_pack_settings = palette_pack_settings

        self._icon_file_name = icon_file_name
        self._cursor = None

    @property
    def palette_pack_settings(self) -> PalettePackSettings:
        return self._palette_pack_settings

    @property
    def icon_file_name(self) -> str:
        return self._icon_file_name

    @property
    def cursor(self) -> QCursor | None:
        if self._cursor is None and self._icon_file_name:
            cursor_icon = QPixmap(self._icon_file_name, format=b'svg')
            self._cursor = QCursor(cursor_icon, hotX=0, hotY=0)
        return self._cursor

    @classmethod
    def from_config(cls, config: UnitedConfig, palette_pack_settings: PalettePackSettings) -> ViewerToolSettings:
        return cls(palette_pack_settings)


class ViewerToolSettingsWidget(QWidget):
    def __init__(self, tool_settings: ViewerToolSettings, parent: QWidget = None):
        super().__init__(parent)

        self._tool_settings = tool_settings

    @property
    def tool_settings(self) -> ViewerToolSettings:
        return self._tool_settings


class ViewerTool(QObject):
    def __init__(self, viewer: DataViewer, undo_manager: UndoManager, settings: ViewerToolSettings):
        super().__init__()

        self.viewer = viewer
        self._undo_manager = undo_manager
        self._settings = settings

        self._original_focus_proxy = None

    @property
    def settings(self) -> ViewerToolSettings:
        return self._settings

    def activate(self):
        if self._settings.cursor is not None:
            self.viewer.viewport.setCursor(self._settings.cursor)

        # Save the current focus proxy and set it to None temporarily
        # to allow key events to be processed in the event filter.
        # Ref: https://stackoverflow.com/questions/2445997/qgraphicsview-and-eventfilter
        self._original_focus_proxy = self.viewer.viewport.focusProxy()
        self.viewer.viewport.setFocusProxy(None)

        if self.viewer.viewport.underMouse():
            # Set focus to ensure the viewport captures key events, as it loses focus after switching tools
            self.viewer.viewport.setFocus()

        self.viewer.viewport.installEventFilter(self)

    def deactivate(self):
        self.viewer.viewport.removeEventFilter(self)
        self.viewer.viewport.setFocusProxy(self._original_focus_proxy)
        self.viewer.viewport.unsetCursor()

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() is QEvent.Type.Enter:
            # Set focus to ensure the viewport captures key events.
            # Otherwise, key events will be processed by other widgets that have focus.
            # For example, instead of switching tools using digits '1', '2', etc.,
            # the digit will be entered into a QLineEdit if it currently has focus.
            self.viewer.viewport.setFocus()

        return super().eventFilter(watched_obj, event)


class LayeredImageViewerToolSettings(ViewerToolSettings):
    def __init__(self, layers_props: dict, palette_pack_settings: PalettePackSettings, icon_file_name: str = ''):
        super().__init__(palette_pack_settings, icon_file_name)

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

    @staticmethod
    def layers_props_from_config(config: UnitedConfig) -> dict:
        return config.value('layers')

    @classmethod
    def from_config(
            cls, config: UnitedConfig, palette_pack_settings: PalettePackSettings) -> LayeredImageViewerToolSettings:
        return cls(cls.layers_props_from_config(config), palette_pack_settings)


class LayeredImageViewerTool(ViewerTool):
    def __init__(
            self,
            viewer: LayeredImageViewer,
            undo_manager: UndoManager,
            settings: LayeredImageViewerToolSettings,
    ):
        super().__init__(viewer, undo_manager, settings)

        self.image_layer_view = None
        self.mask_layer = None
        self.tool_mask_layer = None

        # self.image = None
        # self.mask = None
        # self.tool_mask = None

    @property
    def settings(self) -> LayeredImageViewerToolSettings:
        return cast(LayeredImageViewerToolSettings, self._settings)

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
    def mask_palette(self) -> Palette:
        return self.settings.mask_palette

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
        self.viewer.disable_panning()

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

        self.viewer.enable_panning()

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
                'mask', LAYER_NAME_PROPERTY_KEY, self.image_layer_view.image, self.mask_palette)
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
