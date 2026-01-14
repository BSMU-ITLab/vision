from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from bsmu.vision.core.plugins import Plugin
from bsmu.vision.plugins.windows.main import ViewMenu
from bsmu.vision.widgets.viewers.layered import LayeredDataViewerHolder

if TYPE_CHECKING:
    from bsmu.vision.widgets.viewers.layered import LayeredDataViewer
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi


class MdiImageViewerLayerControllerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(self, main_window_plugin: MainWindowPlugin, mdi_plugin: MdiPlugin):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._layer_controller: MdiImageViewerLayerController | None = None

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._layer_controller = MdiImageViewerLayerController(self._mdi)

        menu_action = self._main_window.add_menu_action(
            ViewMenu,
            'Active Layer View',
            self._layer_controller.toggle_active_layer_view,
            self.tr('E'),
        )
        # menu_action.setCheckable(True)
        menu_action.setWhatsThis('Show active layer and hide other layers / Restore')

    def _disable(self):
        self._layer_controller = None

        raise NotImplementedError


class MdiImageViewerLayerController(QObject):
    def __init__(self, mdi: Mdi):
        super().__init__()

        self.mdi = mdi

        self.sub_windows_layer_controllers = {}  # DataViewerSubWindow: ImageViewerLayerController

    def toggle_active_layer_view(self):
        layer_controller = self._sub_window_layer_controller()
        if layer_controller is not None:
            layer_controller.toggle_active_layer_view()

    def _sub_window_layer_controller(self):
        active_sub_window = self.mdi.activeSubWindow()
        if not isinstance(active_sub_window, LayeredDataViewerHolder):
            return None

        layer_controller = self.sub_windows_layer_controllers.get(active_sub_window)
        if layer_controller is None:
            layer_controller = ImageViewerLayerController(active_sub_window.layered_data_viewer)
            self.sub_windows_layer_controllers[active_sub_window] = layer_controller
        return layer_controller


class ImageViewerLayerController(QObject):
    def __init__(self, image_viewer: LayeredDataViewer):
        super().__init__()

        self.image_viewer = image_viewer

        self._active_layer_view_toggled = False

        self._initial_layers_visibilities = {}  # {layer: visible} (to restore initial state)

    def toggle_active_layer_view(self):
        if self._active_layer_view_toggled:
            # Restore initial state
            for layer_actor in self.image_viewer.layer_actors:
                initial_layer_visibility = self._initial_layers_visibilities.get(layer_actor)
                if initial_layer_visibility is not None:
                    layer_actor.layer.visible = initial_layer_visibility
        else:
            self._initial_layers_visibilities.clear()

            for layer_actor in self.image_viewer.layer_actors:
                # Save initial state
                self._initial_layers_visibilities[layer_actor] = layer_actor.layer.visible
                if layer_actor != self.image_viewer.active_layer_actor:
                    layer_actor.layer.visible = False
            if self.image_viewer.active_layer_actor:
                self.image_viewer.active_layer_actor.layer.visible = True

        self._active_layer_view_toggled = not self._active_layer_view_toggled
