from __future__ import annotations

from bsmu.vision.plugin import Plugin




from plugins.image_viewer.image_viewer import ImageViewer
from plugins.image_viewer.model_image_viewer import ModelImageViewer
from plugins.window.main import MainWindowPlugin

from PyQt5.QtCore import Qt


class LayeredImageViewerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        main_window_plugin = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin')

        self.image_viewer = LayeredImageViewer(self.main_window)

        self.toggle_mask_visibility_action = None

    def _enable(self):
        self.main_window.setCentralWidget(self.image_viewer)

        view_menu = self.main_window.menuBar().addMenu('View')
        self.toggle_mask_visibility_action = view_menu.addAction(
            'Show/Hide Mask', self.image_viewer.toogle_mask_visibility, Qt.CTRL + Qt.Key_M)

        toggle_image_view_action = view_menu.addAction(
            'Image View', self.image_viewer.toogle_image_view, Qt.CTRL + Qt.Key_I)

        view_menu.addAction('Next Image', self.image_viewer.show_next_image, Qt.CTRL + Qt.Key_Right)
        view_menu.addAction('Previous Image', self.image_viewer.show_previous_image, Qt.CTRL + Qt.Key_Left)
