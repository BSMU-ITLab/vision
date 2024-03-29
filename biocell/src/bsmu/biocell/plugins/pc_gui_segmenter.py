from __future__ import annotations

from enum import Enum
from functools import partial
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject

from bsmu.biocell.plugins.pc_segmenter import SegmentationMode
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.visibility import Visibility
from bsmu.vision.plugins.windows.main import AlgorithmsMenu
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from typing import Sequence, Callable

    from bsmu.biocell.plugins.pc_segmenter import PcSegmenter, PcGleasonSegmenter, PcSegmenterPlugin
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin, PalettePackSettings
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class PcGuiSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'pc_segmenter_plugin': 'bsmu.biocell.plugins.pc_segmenter.PcSegmenterPlugin',
        'data_visualization_manager_plugin':
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            pc_segmenter_plugin: PcSegmenterPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._pc_segmenter_plugin = pc_segmenter_plugin

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager

        self._palette_pack_settings_plugin = palette_pack_settings_plugin
        self._palette_pack_settings: PalettePackSettings | None = None

        self._pc_gleason_3_gui_segmenter: PcGleasonGuiSegmenter | None = None
        self._pc_gleason_4_gui_segmenter: PcGleasonGuiSegmenter | None = None

        self._pc_gui_segmenter: PcGuiSegmenter | None = None

    @property
    def pc_gleason_3_gui_segmenter(self) -> PcGleasonGuiSegmenter | None:
        return self._pc_gleason_3_gui_segmenter

    @property
    def pc_gleason_4_gui_segmenter(self) -> PcGleasonGuiSegmenter | None:
        return self._pc_gleason_4_gui_segmenter

    @property
    def pc_gui_segmenter(self) -> PcGuiSegmenter | None:
        return self._pc_gui_segmenter

    def _enable(self):
        self._palette_pack_settings = self._palette_pack_settings_plugin.settings

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager
        # self._data_visualization_manager.data_visualized.connect(self._pc_gleason_3_segmenter.on_data_visualized)

        self._pc_gleason_3_gui_segmenter = PcGleasonGuiSegmenter(
            self._pc_segmenter_plugin.pc_gleason_3_segmenter, self._mdi)
        self._pc_gleason_4_gui_segmenter = PcGleasonGuiSegmenter(
            self._pc_segmenter_plugin.pc_gleason_4_segmenter, self._mdi)

        self._pc_gui_segmenter = PcGuiSegmenter(
            self._pc_segmenter_plugin.pc_segmenter,
            [self._pc_gleason_3_gui_segmenter, self._pc_gleason_4_gui_segmenter],
            self._mdi,
        )

        # self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Prostate Tissue', self._segment_prostate_tissue)

        self._add_segmentation_submenu(
            self.tr('Segment Cancer'),
            partial(self._pc_gui_segmenter.segment_async, mask_layer_name='masks'),
        )
        self._add_segmentation_submenu(
            self.tr('Segment Gleason >= 3'),
            partial(self._pc_gleason_3_gui_segmenter.segment_async, mask_layer_name='gleason >= 3'),
        )
        self._add_segmentation_submenu(
            self.tr('Segment Gleason >= 4'),
            partial(self._pc_gleason_4_gui_segmenter.segment_async, mask_layer_name='gleason >= 4'),
        )

    def _disable(self):
        self._pc_gui_segmenter = None
        self._pc_gleason_3_gui_segmenter = None
        self._pc_gleason_4_gui_segmenter = None

        self._data_visualization_manager = None

        self._mdi = None
        self._main_window = None

        self._palette_pack_settings = None

        raise NotImplementedError

    def _add_segmentation_submenu(self, title: str, method: Callable):
        submenu = self._main_window.add_submenu(AlgorithmsMenu, title)
        for segmentation_mode in SegmentationMode:
            submenu.addAction(segmentation_mode.display_name, partial(method, segmentation_mode=segmentation_mode))

    def _segment_prostate_tissue(self):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        tissue_layer_name = 'prostate-tissue'

        image = layered_image.layers[0].image.pixels
        tissue_mask = segment_tissue(image)
        print('Tissue mask: ', tissue_mask.dtype, tissue_mask.shape, tissue_mask.min(), tissue_mask.max(), np.unique(tissue_mask))
        layered_image.add_layer_or_modify_pixels(
            tissue_layer_name,
            tissue_mask,
            FlatImage,
            Palette.default_binary(rgb_color=[100, 255, 100]),
            Visibility(True, 0.5),
        )


def segment_tissue(image: np.ndarray) -> np.ndarray:
    var = image - image.mean(-1, dtype=np.int16, keepdims=True)
    var = abs(var).mean(-1, dtype=np.uint16)
    tissue_mask = np.where(var > 2, True, False).astype(np.uint8)
    return tissue_mask


class MaskDrawMode(Enum):
    REDRAW_ALL = 1
    """Completely replace the existing mask with the new mask."""

    OVERLAY_FOREGROUND = 2
    """Apply the new mask only where its own pixels are equal to foreground value,
    preserving the existing mask elsewhere."""

    FILL_BACKGROUND = 3
    """Apply the new mask only on the background pixels of the existing mask, leaving other pixels unchanged."""


class MdiSegmenter(QObject):
    def __init__(self, mdi: Mdi):
        super().__init__()

        self._mdi = mdi

    def _active_layered_image(self) -> LayeredImage | None:
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        return layered_image_viewer_sub_window and layered_image_viewer_sub_window.layered_image_viewer.data


class PcGuiSegmenter(MdiSegmenter):
    def __init__(self, pc_segmenter: PcSegmenter, class_gui_segmenters: Sequence[PcGleasonGuiSegmenter], mdi: Mdi):
        super().__init__(mdi)

        self._pc_segmenter = pc_segmenter
        self._class_gui_segmenters = class_gui_segmenters

    def segment_async(
            self,
            mask_layer_name: str,
            segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY,
            mask_draw_mode: MaskDrawMode = MaskDrawMode.REDRAW_ALL,
    ):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        image_layer = layered_image.layers[0]
        image = image_layer.image
        on_finished = partial(
            self._on_pc_segmentation_finished,
            layered_image=layered_image,
            mask_layer_name=mask_layer_name,
            mask_draw_mode=mask_draw_mode,
        )
        self._pc_segmenter.segment_async(image, segmentation_mode, on_finished)

    def _on_pc_segmentation_finished(
            self,
            masks: Sequence[np.ndarray],
            layered_image: LayeredImage,
            mask_layer_name: str,
            mask_draw_mode: MaskDrawMode = MaskDrawMode.REDRAW_ALL,
    ):
        # Apply the passed `mask_draw_mode` only to draw the first mask
        first = 0
        modifiable_mask = self._class_gui_segmenters[first].update_mask_layer(
            masks[first], layered_image, mask_layer_name, mask_draw_mode)

        # Apply other draw modes for subsequent masks to preserve already drawn masks
        if mask_draw_mode == MaskDrawMode.REDRAW_ALL or mask_draw_mode == MaskDrawMode.OVERLAY_FOREGROUND:
            update_mask_layer = partial(self._update_mask_layer, mask_draw_mode=MaskDrawMode.OVERLAY_FOREGROUND)
        elif mask_draw_mode == MaskDrawMode.FILL_BACKGROUND:
            update_mask_layer = partial(self._update_mask_layer_partially, modifiable_mask=modifiable_mask)
        else:
            raise ValueError(f'Invalid MaskDrawMode: {mask_draw_mode}')

        for class_gui_segmenter, mask in zip(self._class_gui_segmenters[1:], masks[1:]):
            update_mask_layer(class_gui_segmenter, mask, layered_image, mask_layer_name)

    @staticmethod
    def _update_mask_layer(
            class_gui_segmenter: PcGleasonGuiSegmenter,
            mask: np.ndarray,
            layered_image: LayeredImage,
            mask_layer_name: str,
            mask_draw_mode: MaskDrawMode,
    ):
        class_gui_segmenter.update_mask_layer(mask, layered_image, mask_layer_name, mask_draw_mode)

    @staticmethod
    def _update_mask_layer_partially(
            class_gui_segmenter: PcGleasonGuiSegmenter,
            mask: np.ndarray,
            layered_image: LayeredImage,
            mask_layer_name: str,
            modifiable_mask: np.ndarray,
    ):
        class_gui_segmenter.update_mask_layer_partially(mask, layered_image, mask_layer_name, modifiable_mask)


class PcGleasonGuiSegmenter(MdiSegmenter):
    def __init__(self, pc_gleason_segmenter: PcGleasonSegmenter, mdi: Mdi):
        super().__init__(mdi)

        self._pc_gleason_segmenter = pc_gleason_segmenter

    @property
    def mask_foreground_class(self) -> int:
        return self._pc_gleason_segmenter.mask_foreground_class

    @property
    def mask_background_class(self) -> int:
        return self._pc_gleason_segmenter.mask_background_class

    def segment_async(
            self,
            mask_layer_name: str,
            segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY,
            mask_draw_mode: MaskDrawMode = MaskDrawMode.REDRAW_ALL,
    ):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        image_layer = layered_image.layers[0]
        image = image_layer.image
        on_finished = partial(
            self._on_pc_gleason_segmentation_finished,
            layered_image=layered_image,
            mask_layer_name=mask_layer_name,
            mask_draw_mode=mask_draw_mode,
        )
        self._pc_gleason_segmenter.segment_async(image, segmentation_mode, on_finished)

    def _on_pc_gleason_segmentation_finished(
            self,
            mask: np.ndarray,
            layered_image: LayeredImage,
            mask_layer_name: str,
            mask_draw_mode: MaskDrawMode = MaskDrawMode.REDRAW_ALL,
    ):
        self.update_mask_layer(mask, layered_image, mask_layer_name, mask_draw_mode)

    def update_mask_layer_partially(
            self,
            mask: np.ndarray,
            layered_image: LayeredImage,
            mask_layer_name: str,
            modifiable_mask: np.ndarray | None,
    ):
        mask_layer = layered_image.layer_by_name(mask_layer_name)
        is_foreground_class = mask == self.mask_foreground_class
        if modifiable_mask is not None:
            is_foreground_class &= modifiable_mask
        mask_layer.image_pixels[is_foreground_class] = self.mask_foreground_class
        mask_layer.image.emit_pixels_modified()

    def update_mask_layer(
            self,
            mask: np.ndarray,
            layered_image: LayeredImage,
            mask_layer_name: str,
            mask_draw_mode: MaskDrawMode = MaskDrawMode.REDRAW_ALL,
    ) -> np.ndarray | None:
        mask_layer = layered_image.layer_by_name(mask_layer_name)
        is_modified = None
        if mask_draw_mode == MaskDrawMode.REDRAW_ALL or mask_layer is None or not mask_layer.is_image_pixels_valid:
            layered_image.add_layer_or_modify_pixels(
                mask_layer_name,
                mask,
                FlatImage,
                self._pc_gleason_segmenter.mask_palette,
                Visibility(True, 0.5),
            )
        elif mask_draw_mode == MaskDrawMode.OVERLAY_FOREGROUND:
            is_modified = mask == self.mask_foreground_class
            mask_layer.image_pixels[is_modified] = self.mask_foreground_class
            mask_layer.image.emit_pixels_modified()
        elif mask_draw_mode == MaskDrawMode.FILL_BACKGROUND:
            is_modified = mask_layer.image_pixels == self.mask_background_class
            mask_layer.image_pixels[is_modified] = mask[is_modified]
            mask_layer.image.emit_pixels_modified()
        else:
            raise ValueError(f'Invalid MaskDrawMode: {mask_draw_mode}')
        return is_modified

    def on_data_visualized(self, data: Data, data_viewer_sub_windows: list[DataViewerSubWindow]):
        raise NotImplementedError

        mask_layer_name = self._pc_gleason_segmenter.segmenter.model_params.output_object_name
        if not isinstance(data, LayeredImage) or (len(data.layers) > 1 and data.layers[1].name == mask_layer_name):
            return

        self.segment_async(mask_layer_name, data)
