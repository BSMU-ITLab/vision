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

        self.file_dropper = FileDropper(file_loading_manager_plugin.file_loading_manager,
                                        data_visualization_manager_plugin.data_visualization_manager)

    def _enable(self):
        self.mdi.setAcceptDrops(True)
        self.mdi.installEventFilter(self.file_dropper)

    def _disable(self):
        self.mdi.removeEventFilter(self.file_dropper)


class FileDropper(QObject):
    def __init__(self, file_loading_manager: FileLoadingManager, visualization_manager: DataVisualizationManager):
        super().__init__()

        self.file_loading_manager = file_loading_manager
        self.visualization_manager = visualization_manager
        self.dragged_file_path = None

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
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            self.dragged_file_path = Path(mime_data.urls()[0].toLocalFile())
            print(self.dragged_file_path)
            if self.file_loading_manager.can_load_file(self.dragged_file_path):
                event.accept()
                return
        event.ignore()

    def on_drop(self, event):
        print('drop', self.dragged_file_path)
        data = self.file_loading_manager.load_file(self.dragged_file_path)
        self.visualization_manager.visualize_data(data)
