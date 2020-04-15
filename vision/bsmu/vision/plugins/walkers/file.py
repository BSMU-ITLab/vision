from __future__ import annotations

import os

from PySide2.QtCore import QObject, Qt

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import MenuType
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow


class MdiImageLayerFileWalkerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi
        file_loading_manager = app.enable_plugin(
            'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin').file_loading_manager

        self.mdi_image_layer_file_walker = MdiImageLayerFileWalker(mdi, file_loading_manager)

    def _enable(self):
        self.main_window.add_menu_action(MenuType.VIEW, 'Next Image',
                                         self.mdi_image_layer_file_walker.show_next_image,
                                         Qt.CTRL + Qt.Key_Right)
        self.main_window.add_menu_action(MenuType.VIEW, 'Previous Image',
                                         self.mdi_image_layer_file_walker.show_previous_image,
                                         Qt.CTRL + Qt.Key_Left)

    def _disable(self):
        raise NotImplementedError


class MdiImageLayerFileWalker(QObject):
    def __init__(self, mdi: Mdi, file_loading_manager: FileLoadingManager):
        super().__init__()

        self.mdi = mdi
        self.file_loading_manager = file_loading_manager

        self.image_layer_file_walkers = {}  # DataViewerSubWindow: ImageLayerFileWalker

    def show_next_image(self):
        walker = self._image_layer_file_walker()
        if walker is not None:
            walker.show_next_image()

    def show_previous_image(self):
        walker = self._image_layer_file_walker()
        if walker is not None:
            walker.show_previous_image()

    def _image_layer_file_walker(self):
        active_sub_window = self.mdi.activeSubWindow()
        if not isinstance(active_sub_window, LayeredImageViewerSubWindow):
            return None

        image_layer_file_walker = self.image_layer_file_walkers.get(active_sub_window)
        if image_layer_file_walker is None:
            image_layer_file_walker = ImageLayerFileWalker(active_sub_window.viewer, self.file_loading_manager)
            self.image_layer_file_walkers[active_sub_window] = image_layer_file_walker
        return image_layer_file_walker


class ImageLayerFileWalker(QObject):
    def __init__(self, image_viewer: LayeredImageViewer, file_loading_manager: FileLoadingManager):
        super().__init__()

        self.image_viewer = image_viewer
        self.file_loading_manager = file_loading_manager

        self._main_layer_image_dir = None
        self._main_layer_dir_images = None
        self._main_layer_image_index = None

    @property
    def active_layer(self):
        return self.image_viewer.active_layer_view

    @property
    def main_layer_image_dir(self):
        if self._main_layer_image_dir is None:
            self._main_layer_image_dir = self.active_layer.image_path.parent
        return self._main_layer_image_dir

    @property
    def main_layer_dir_images(self):
        if self._main_layer_dir_images is None:
            self._main_layer_dir_images = sorted(os.listdir(self.main_layer_image_dir))
        return self._main_layer_dir_images

    @property
    def main_layer_image_index(self):
        if self._main_layer_image_index is None:
            self._main_layer_image_index = self.main_layer_dir_images.index(self.active_layer.image_path.name)
        return self._main_layer_image_index

    def show_next_image(self):
        self._show_image_with_index(self.main_layer_image_index + 1)

    def show_previous_image(self):
        self._show_image_with_index(self.main_layer_image_index - 1)

    def _show_image_with_index(self, index: int):
        index = index % len(self.main_layer_dir_images)
        next_file_name = self.main_layer_dir_images[index]
        # next_file_path = self.main_layer_image_dir / next_file_name
        # next_image = self.loading_manager.load_file(next_file_path)
        # self.main_layer.image = next_image
        self._main_layer_image_index = index

        # update images of all layers
        for layer in self.image_viewer.layers:
            # Load new image, but use palette of old image (so, if palette is not None, image will be loaded as gray)
            if layer.path is not None:
                file_path = layer.path / next_file_name
                layer.image = self.file_loading_manager.load_file(file_path, palette=layer.palette)
