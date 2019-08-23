import sys
from pathlib import Path

from PySide2.QtCore import Signal
from PySide2.QtWidgets import QApplication

from bsmu.vision.app.config import Config
from bsmu.vision.app.plugin import Plugin
from bsmu.vision.app.plugin_manager import PluginManager


CONFIG_FILE_PATH = (Path(__file__).parent / 'App.conf.yaml').resolve()


class App(QApplication):
    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self, argv, childs=()):
        super().__init__(argv)

        self.childs = childs
        print('childs:', childs)
        print('module', App.__module__)
        print(sys.modules[self.__module__].__file__)
        # exit()


        from bsmu.vision.app.config_uniter import ConfigUniter
        self.config_uniter = ConfigUniter(childs)

        united_config = self.config_uniter.unite_configs(Path(__file__).parent, 'App.conf.yaml')
        print('united_config:', united_config.data)
        # exit()



        '''
        from skimage.io import imread
        from PySide2.QtCore import Qt
        from PySide2.QtGui import QPixmap
        from PySide2.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QLabel, QShortcut
        from bsmu.vision_core.converters.image import numpy_rgba_image_to_qimage, converted_to_rgba
        from bsmu.vision_core.image import FlatImage
        from bsmu.vision.widgets.viewers.graphics_view import GraphicsView
        from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer

        image = imread('../../../tests/images/spacex.jpg')

        flat_image = FlatImage(image)
        self.layered_image_viewer = LayeredImageViewer(flat_image, zoomable=True)
        self.layered_image_viewer.show()
        # self.layered_image_viewer.setGeometry(200, 200, 1000, 600)
        self.shortcut = QShortcut(Qt.CTRL + Qt.Key_Right, self.layered_image_viewer, self.layered_image_viewer.center)
        '''

        '''
        print(type(image), image.shape, image.dtype)
        image = converted_to_rgba(image)
        print(type(image), image.shape, image.dtype)

        self.qimage = numpy_rgba_image_to_qimage(image)
        pixmap = QPixmap.fromImage(self.qimage)

        pixmap_item = QGraphicsPixmapItem(pixmap)
        pixmap_item.setTransformationMode(Qt.SmoothTransformation)

        scene = QGraphicsScene()
        scene.addItem(pixmap_item)

        self.view = GraphicsView(scene, zoomable=True)
        self.view.show()
        '''

        print(f'App started. Prefix: {sys.prefix}')

        self.config = Config(CONFIG_FILE_PATH)
        self.config.load()
        print(f'Config:\n{self.config.data}')

        self.plugin_manager = PluginManager(self)
        self.plugin_manager.plugin_enabled.connect(self.plugin_enabled)
        self.plugin_manager.plugin_disabled.connect(self.plugin_disabled)

        if self.config.data is not None:
            self.plugin_manager.enable_plugins(self.config.data['plugins'])

        # self.aboutToQuit.connect(self.config.config)

    def enable_plugin(self, full_name: str):
        return self.plugin_manager.enable_plugin(full_name)

    def enabled_plugins(self):
        return self.plugin_manager.enabled_plugins

    def run(self):
        sys.exit(self.exec_())
