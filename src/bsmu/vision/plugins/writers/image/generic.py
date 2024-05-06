from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import skimage.io
from PySide6.QtWidgets import QFileDialog, QMessageBox

from bsmu.vision.plugins.windows.main import FileMenu
from bsmu.vision.plugins.writers.base import FileWriterPlugin, FileWriter
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from bsmu.vision.core.image.base import Image
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi


class GenericImageFileWriterPlugin(FileWriterPlugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
    ):
        super().__init__(GenericImageFileWriter)

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._last_saved_file_dir = None

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._main_window.add_menu_action(FileMenu, 'Save Mask', self._save_active_window_image)
        self._main_window.add_menu_action(FileMenu, 'Save Mask As...', self._select_path_and_save_active_window_image)

        self._mdi = self._mdi_plugin.mdi

    def _active_window_image(self) -> tuple[Image | None, Path | None]:
        """
        :return: path is the active layer path (to use as default save directory)
        """
        active_sub_window = self._mdi.activeSubWindow()
        if not isinstance(active_sub_window, LayeredImageViewerHolder):
            QMessageBox.warning(
                self._main_window,
                'No Layered Image',
                'The active window does not contain a layered image.')
            return None, None

        layer_name = 'masks'
        active_layered_image_viewer = active_sub_window.layered_image_viewer
        image_layer = active_layered_image_viewer.layer_by_name(layer_name)
        if not image_layer or not image_layer.image:
            QMessageBox.warning(
                self._main_window,
                'No Image',
                f'The layered image does not contain an image in the <{layer_name}> layer.')
            return None, None

        return image_layer.image, active_layered_image_viewer.active_layer.path

    def _save_active_window_image(self):
        image, active_layer_path = self._active_window_image()
        if image is None:
            return

        if image.path is None:
            self._select_path_and_save_image(image, active_layer_path)
        else:
            self._save_image(image, image.path)

    def _select_path_and_save_active_window_image(self):
        image, active_layer_path = self._active_window_image()
        if image is None:
            return

        self._select_path_and_save_image(image, active_layer_path)

    def _select_path_and_save_image(self, image: Image, dialog_dir: Path = None):
        if image.path is not None:
            dialog_dir = image.path
        elif self._last_saved_file_dir is not None:
            dialog_dir = self._last_saved_file_dir
        dialog_dir_str = '' if dialog_dir is None else str(dialog_dir)
        file_name, selected_filter = QFileDialog.getSaveFileName(
            parent=self._main_window, caption='Save Mask', dir=dialog_dir_str, filter='PNG (*.png)')
        if not file_name:
            return
        self._last_saved_file_dir = Path(file_name).parent

        save_path = Path(file_name)
        if self._save_image(image, save_path):
            image.path = save_path

    def _save_image(self, image: Image, path: Path) -> bool:
        try:
            self._file_writer_cls().write_to_file(image, path)
            return True
        except Exception as e:
            QMessageBox.warning(
                self._main_window,
                'Save Error',
                f'Cannot save the image.\n{e}')
            return False


class GenericImageFileWriter(FileWriter):
    _FORMATS = ('png', 'jpg', 'jpeg', 'bmp', 'tif', 'tiff')

    def _write_to_file(self, data: Image, path: Path, **kwargs):
        # TODO: move the logging into base class
        logging.info(f'Write Generic Image: {path}')

        # TODO: use OpenCV to save the image (compare performance and size of the resulting files)
        skimage.io.imsave(str(path), data.pixels, check_contrast=False)
