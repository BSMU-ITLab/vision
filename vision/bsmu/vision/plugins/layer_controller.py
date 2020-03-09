from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Qt

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import MenuType
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow

if TYPE_CHECKING:
    from bsmu.vision.app import App
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer
    from bsmu.vision.plugins.doc_interfaces.mdi import Mdi


class MdiImageViewerLayerControllerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi

        self.mdi_layer_controller = MdiImageViewerLayerController(mdi)

    def _enable(self):
        menu_action = self.main_window.add_menu_action(
            MenuType.VIEW, 'Active Layer View', self.mdi_layer_controller.toggle_active_layer_view,
            Qt.CTRL + Qt.Key_I)
        # menu_action.setCheckable(True)
        menu_action.setWhatsThis('Show active layer and hide other layers / Restore')

    def _disable(self):
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
        if not isinstance(active_sub_window, LayeredImageViewerSubWindow):
            return None

        layer_controller = self.sub_windows_layer_controllers.get(active_sub_window)
        if layer_controller is None:
            layer_controller = ImageViewerLayerController(active_sub_window.viewer)
            self.sub_windows_layer_controllers[active_sub_window] = layer_controller
        return layer_controller


class ImageViewerLayerController(QObject):
    def __init__(self, image_viewer: LayeredImageViewer):
        super().__init__()

        self.image_viewer = image_viewer

        self._active_layer_view_toggled = False

        self._initial_layers_visibilities = {}  # {layer: visible} (to restore initial state)

    def toggle_active_layer_view(self):
        if self._active_layer_view_toggled:
            # Restore initial state
            for layer in self.image_viewer.layers:
                initial_layer_visibility = self._initial_layers_visibilities.get(layer)
                if initial_layer_visibility is not None:
                    layer.visible = initial_layer_visibility
        else:
            self._initial_layers_visibilities.clear()

            for layer in self.image_viewer.layers:
                # Save initial state
                self._initial_layers_visibilities[layer] = layer.visible
                layer.visible = False
            self.image_viewer.active_layer.visible = True

        self._active_layer_view_toggled = not self._active_layer_view_toggled
