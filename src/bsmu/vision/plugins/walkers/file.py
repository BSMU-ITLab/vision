from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import ViewMenu
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow

if TYPE_CHECKING:
    from pathlib import Path

    from bsmu.vision.core.image import ImageLayer
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.widgets.viewers.image import LayeredImageViewer


class MdiImageLayerFileWalkerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'file_loading_manager_plugin': 'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._file_loading_manager_plugin = file_loading_manager_plugin
        self._file_loading_manager: FileLoadingManager | None = None

        self._mdi_image_layer_file_walker: MdiImageLayerFileWalker | None = None

    @property
    def mdi_image_layer_file_walker(self) -> MdiImageLayerFileWalker:
        return self._mdi_image_layer_file_walker

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager

        self._mdi_image_layer_file_walker = MdiImageLayerFileWalker(
            self._mdi,
            self._file_loading_manager,
            self.config_value('extensions'),
        )

        self._main_window.add_menu_action(
            ViewMenu, 'Next Image', self._mdi_image_layer_file_walker.show_next_image, Qt.CTRL | Qt.Key_Right)
        self._main_window.add_menu_action(
            ViewMenu, 'Previous Image', self._mdi_image_layer_file_walker.show_previous_image, Qt.CTRL | Qt.Key_Left)

    def _disable(self):
        self._mdi_image_layer_file_walker = None

        raise NotImplementedError


class MdiImageLayerFileWalker(QObject):
    def __init__(self, mdi: Mdi, file_loading_manager: FileLoadingManager, allowed_extensions: list[str] | None):
        super().__init__()

        self.mdi = mdi
        self.file_loading_manager = file_loading_manager

        self.image_layer_file_walkers = {}  # DataViewerSubWindow: ImageLayerFileWalker
        self.allowed_extensions = allowed_extensions

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
            image_layer_file_walker = ImageLayerFileWalker(
                active_sub_window.viewer, self.file_loading_manager, self.allowed_extensions)
            self.image_layer_file_walkers[active_sub_window] = image_layer_file_walker
        return image_layer_file_walker


class ImageLayerFileWalker(QObject):
    def __init__(
            self,
            image_viewer: LayeredImageViewer,
            file_loading_manager: FileLoadingManager,
            allowed_extensions: list[str] | None,
    ):
        super().__init__()
        self.image_viewer = image_viewer
        self.file_loading_manager = file_loading_manager
        self.allowed_extensions = allowed_extensions

        self._main_layer_dir: Path | None = None
        self._main_layer_dir_images: list[Path] | None = None
        self._main_layer_image_index: int | None = None

    @property
    def active_layer(self) -> ImageLayer:
        return self.image_viewer.active_layer

    @property
    def main_layer_dir(self) -> Path | None:
        if self._main_layer_dir is None:
            self._main_layer_dir = self.active_layer.path
        return self._main_layer_dir

    @property
    def main_layer_dir_images(self) -> list[Path] | None:
        if self._main_layer_dir_images is None:
            # TODO: add support of compound extensions, e.g. `.nii.gz`
            # TODO: try to use itertools.cycle and iterdir() generator instead of storing file names in the list
            # Generate list of file names with allowed extensions
            self._main_layer_dir_images = sorted(
                [
                    file_path.relative_to(self.main_layer_dir) for file_path in self.main_layer_dir.rglob('*')
                    if self.allowed_extensions is None or file_path.suffix[1:] in self.allowed_extensions
                ]
            )
        return self._main_layer_dir_images

    @property
    def main_layer_image_index(self) -> int | None:
        if self._main_layer_image_index is None:
            self._main_layer_image_index = self.main_layer_dir_images.index(
                self.active_layer.image_path.relative_to(self.main_layer_dir))
        return self._main_layer_image_index

    def show_next_image(self):
        self._show_image_with_index(self.main_layer_image_index + 1)

    def show_previous_image(self):
        self._show_image_with_index(self.main_layer_image_index - 1)

    def _show_image_with_index(self, index: int):
        self._main_layer_image_index = index % len(self.main_layer_dir_images)
        next_file_relative_path = self.main_layer_dir_images[self._main_layer_image_index]
        # Update images of all layers
        for layer in self.image_viewer.layers:
            if layer.path is None:
                continue

            # Load new image, but use palette of old image (so, if palette is not None, image will be loaded as gray)
            file_path = layer.path / next_file_relative_path
            if layer != self.image_viewer.active_layer and layer.extension is not None:
                file_path = file_path.with_suffix(layer.extension)
            layer.image = self.file_loading_manager.load_file(file_path, palette=layer.palette)
