from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.visibility import Visibility
from bsmu.vision.plugins.windows.main import AlgorithmsMenu
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from bsmu.biocell.plugins.dnn_tissue_segmenter import DnnTissueSegmenter, DnnTissueSegmenterPlugin
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin, PalettePackSettings
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class GuiDnnTissueSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'dnn_tissue_segmenter_plugin': 'bsmu.biocell.plugins.dnn_tissue_segmenter.DnnTissueSegmenterPlugin',
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            dnn_tissue_segmenter_plugin: DnnTissueSegmenterPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin

        self._dnn_tissue_segmenter_plugin = dnn_tissue_segmenter_plugin

        self._palette_pack_settings_plugin = palette_pack_settings_plugin
        self._palette_pack_settings: PalettePackSettings | None = None

        self._gui_dnn_tissue_segmenter: GuiDnnTissueSegmenter | None = None

    @property
    def gui_dnn_tissue_segmenter(self) -> GuiDnnTissueSegmenter | None:
        return self._gui_dnn_tissue_segmenter

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        mdi = self._mdi_plugin.mdi

        self._gui_dnn_tissue_segmenter = GuiDnnTissueSegmenter(
            self._dnn_tissue_segmenter_plugin.dnn_tissue_segmenter,
            mdi,
        )

        self._main_window.add_menu_action(
            AlgorithmsMenu,
            self.tr('Segment Tissue Using DNN'),
            partial(self._gui_dnn_tissue_segmenter.segment, mask_layer_name='masks'),
        )

    def _disable(self):
        self._gui_dnn_tissue_segmenter = None

        self._main_window = None

        self._palette_pack_settings = None

        raise NotImplementedError


class MdiSegmenter(QObject):
    def __init__(self, mdi: Mdi):
        super().__init__()

        self._mdi = mdi

    def _active_layered_image(self) -> LayeredImage | None:
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        return layered_image_viewer_sub_window and layered_image_viewer_sub_window.layered_image_viewer.data


class GuiDnnTissueSegmenter(MdiSegmenter):
    def __init__(self, dnn_tissue_segmenter: DnnTissueSegmenter, mdi: Mdi):
        super().__init__(mdi)

        self._dnn_tissue_segmenter = dnn_tissue_segmenter

    @property
    def mask_foreground_class(self) -> int:
        return self._dnn_tissue_segmenter.mask_foreground_class

    @property
    def mask_background_class(self) -> int:
        return self._dnn_tissue_segmenter.mask_background_class

    def segment(self, mask_layer_name: str):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        if layered_image.contains_layer(mask_layer_name):
            reply = QMessageBox.question(
                self._mdi,
                self.tr('Non-unique Layer Name'),
                self.tr(
                    'Viewer already contains a layer with such name: {0}. '
                    'Repaint its content?'
                ).format(mask_layer_name),
                defaultButton=QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        image_layer = layered_image.layers[0]
        image = image_layer.image
        mask = self._dnn_tissue_segmenter.segment(image.pixels)

        layered_image.add_layer_or_modify_pixels(
            mask_layer_name,
            mask,
            FlatImage,
            self._dnn_tissue_segmenter.mask_palette,
            Visibility(True, 0.5),
        )
