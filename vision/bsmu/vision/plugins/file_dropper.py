from __future__ import annotations

from pathlib import Path

from PySide2.QtCore import QObject, QEvent

from bsmu.vision.app.plugin import Plugin


class FileDropperPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi
        file_loading_manager_plugin = app.enable_plugin('bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin')
        data_visualization_manager_plugin = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin')
        post_load_conversion_manager = app.enable_plugin(
            'bsmu.vision.plugins.post_load_converters.manager.PostLoadConversionManagerPlugin')\
            .post_load_conversion_manager

        self.file_dropper = FileDropper(file_loading_manager_plugin.file_loading_manager,
                                        post_load_conversion_manager,
                                        data_visualization_manager_plugin.data_visualization_manager)

    def _enable(self):
        self.mdi.setAcceptDrops(True)
        self.mdi.installEventFilter(self.file_dropper)

    def _disable(self):
        self.mdi.removeEventFilter(self.file_dropper)


class FileDropper(QObject):
    def __init__(self, file_loading_manager: FileLoadingManager,
                 post_load_conversion_manager: PostLoadConversionManager,
                 visualization_manager: DataVisualizationManager):
        super().__init__()

        self.file_loading_manager = file_loading_manager
        self.post_load_conversion_manager = post_load_conversion_manager
        self.visualization_manager = visualization_manager

        self.dragged_loadable_file_paths = []

    def eventFilter(self, watched_obj, event):
        if event.type() == QEvent.DragEnter:
            self.on_drag_enter(event)
            return True
        elif event.type() == QEvent.Drop:
            self.on_drop(event)
            return True
        else:
            return super().eventFilter(watched_obj, event)

    def on_drag_enter(self, event):
        self.dragged_loadable_file_paths.clear()

        mime_data = event.mimeData()
        for url in mime_data.urls():
            file_path = Path(url.toLocalFile())
            if self.file_loading_manager.can_load_file(file_path):
                self.dragged_loadable_file_paths.append(file_path)

        event.setAccepted(bool(self.dragged_loadable_file_paths))

    def on_drop(self, event):
        print('drop', self.dragged_loadable_file_paths)
        for file_path in self.dragged_loadable_file_paths:
            data = self.file_loading_manager.load_file(file_path)
            data = self.post_load_conversion_manager.convert_data(data)
            self.visualization_manager.visualize_data(data)
