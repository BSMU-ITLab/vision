from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision_core.image.layered import LayeredImage
from bsmu.vision_core.palette import Palette

if TYPE_CHECKING:
    from bsmu.vision.app import App


class ImageViewerPathOverlayerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.data_visualization_manager = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin').data_visualization_manager
        file_loading_manager_plugin = app.enable_plugin('bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin')

        self.overlayer = ImageViewerPathOverlayer(
            self.data_visualization_manager, file_loading_manager_plugin.file_loading_manager, self.old_config().data)

    def _enable(self):
        self.data_visualization_manager.data_visualized.connect(self.overlayer.overlay_sibling_dirs_images)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(self.overlayer.overlay_sibling_dirs_images)


class ImageViewerPathOverlayer(QObject):
    def __init__(self, visualization_manager: DataVisualizationManager, loading_manager: FileLoadingManager,
                 config_data):
        super().__init__()

        self.visualization_manager = visualization_manager
        self.loading_manager = loading_manager
        self.config_data = config_data

    def overlay_sibling_dirs_images(self, data: Data, data_viewer_sub_windows: DataViewerSubWindow):
        print('overlayyy', type(data))
        if isinstance(data, LayeredImage):
            first_layer = data.layers[0]
            first_layer_image_name = first_layer.image_path.name
            layers_dir = first_layer.path.parent
            print('first_la_path', layers_dir)

            for new_layer_name, layer_properties in self.config_data['layers'].items():
                new_layer_image_path = layers_dir / new_layer_name / first_layer_image_name
                print('CCCCCCCCC', new_layer_image_path)
                if new_layer_image_path.exists():
                    palette_property = layer_properties.get('palette')
                    palette = palette_property and Palette.from_sparse_index_list(list(palette_property))
                    new_image = self.loading_manager.load_file(new_layer_image_path, palette=palette)
                    new_image_layer = data.add_layer_from_image(new_image, new_layer_name)

                    layer_opacity = layer_properties['opacity']
                    for data_viewer_sub_window in data_viewer_sub_windows:
                        layered_image_viewer = data_viewer_sub_window.viewer
                        layered_image_viewer.layer_view_by_model(new_image_layer).opacity = layer_opacity


        # for data_viewer_sub_window in data_viewer_sub_windows:
        #     if isinstance(data_viewer_sub_window, LayeredImageViewerSubWindow):
        #         layered_image_viewer = data_viewer_sub_window.viewer
        #         image_path = layered_image_viewer.active_layer_view.image_path
        #         layers_dir = image_path.parents[1]
        #         for new_layer_name, layer_properties in self.config_data['layers'].items():
        #             layer_image_path = layers_dir / new_layer_name / image_path.name
        #             if layer_image_path.exists():
        #                 palette_property = layer_properties.get('palette')
        #                 palette = palette_property and Palette.from_sparse_index_list(list(palette_property))
        #                 image = self.loading_manager.load_file(layer_image_path, palette=palette)
        #                 layer_opacity = layer_properties['opacity']
        #                 image_layer = layered_image_viewer.add_layer_from_image(image, new_layer_name)
        #                 layered_image_viewer.layer_view_by_model(image_layer).opacity = layer_opacity
