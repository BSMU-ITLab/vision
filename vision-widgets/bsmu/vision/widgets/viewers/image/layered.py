from __future__ import annotations

import os
from functools import partial

from PySide2.QtCore import Qt, QObject, Signal, QTimeLine, QEvent, QRectF, QPointF, QSizeF
from PySide2.QtGui import QPainter
from PySide2.QtWidgets import QGridLayout, QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsEllipseItem

from bsmu.vision_core.image import FlatImage
from bsmu.vision.widgets.viewers.base import DataViewer

# from .base import DataViewer
# from core import FlatImage
# from core.colormap import Colormap
# from core import image_utils
# from core import settings
#
# from PyQt5.QtWidgets import QLabel, QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem, \
#     QStyleOptionGraphicsItem, QWidget, QGridLayout
# from PyQt5.QtGui import QPixmap, QPainter, QMouseEvent, QBrush, QShowEvent, QPaintEvent
# from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimeLine, QPointF, QRectF, QObject, QEvent, QSizeF, QRect
# from skimage.io import imread, imsave
# import numpy as np
# import os
#
# from functools import partial


class ImageViewerLayer(QObject):  #% rename to ImageItemLayer
    max_id = 0

    updated = Signal(FlatImage)

    def __init__(self, name: str = '', image: FlatImage = None, colormap: Colormap = None,
                 visible: bool = True, opacity: float = 1):
        """Colormap only for indexed images"""
        super().__init__()
        self.id = ImageViewerLayer.max_id
        ImageViewerLayer.max_id += 1

        self.name = name if name else 'Layer ' + str(self.id)
        self._image = None
        self.image = image #if image is not None else Image()
        self.colormap = colormap
        self.visible = visible
        self.opacity = opacity

        self._displayed_image_cache = None

    @property
    def image_path(self):
        return self.image.path

    @property  # TODO: this is slow. If we need only setter, there are alternatives without getter
    def image(self):
        return self._image

    @image.setter
    def image(self, value):
        if self._image != value:
            self._image = value
            # self._displayed_image_cache = None
            self._on_image_updated()
            self._image.updated.connect(self._on_image_updated)

    @property
    def displayed_image(self):
        if self._displayed_image_cache is None:
            if self.colormap is None:
                displayed_rgba_array = image_utils.converted_to_normalized_uint8(self.image.array)
                displayed_rgba_array = image_utils.converted_to_rgba(displayed_rgba_array)
            else:
                displayed_rgba_array = self.colormap.colored_premultiplied_image(self.image.array)
            self._displayed_image_cache = image_utils.numpy_rgba_image_to_qimage(displayed_rgba_array)
        return self._displayed_image_cache

    def _on_image_updated(self):
        print('on_image_updated (image array updated or layer image changed) !!!!!!!!!!!!!')
        self._displayed_image_cache = None
        self.updated.emit(self.image)


class _Zoom:  # TODO: Use Python 3.7 dataclasses
    def __init__(self, pos, factor):
        self.pos = pos
        self.factor = factor


class _ZoomTimeLine(QTimeLine):
    def __init__(self, duration: int = 1000, parent: QObject = None):
        super().__init__(duration, parent)

        self.finished.connect(self.deleteLater)


class _ViewSmoothZoom(QObject):
    zoom_finished = Signal()

    def __init__(self, view, parent: QObject = None):
        super().__init__(parent)

        self.view = view

        self.zoom_in_factor = 0.25
        self.zoom_out_factor = -self.zoom_in_factor

    def eventFilter(self, watched_obj, event):
        if event.type() == QEvent.Wheel:
            self.on_wheel_scrolled(event)
            return True
        else:
            return super().eventFilter(watched_obj, event)

    def on_wheel_scrolled(self, event):
        zoom_factor = self.zoom_in_factor if event.angleDelta().y() > 0 else self.zoom_out_factor
        SMOOTH_ZOOM_DURATION = 200
        SMOOTH_ZOOM_UPDATE_INTERVAL = 20
        zoom_factor = 1 + zoom_factor / (SMOOTH_ZOOM_DURATION / SMOOTH_ZOOM_UPDATE_INTERVAL)
        zoom = _Zoom(event.pos(), zoom_factor)
        zoom_time_line = _ZoomTimeLine(SMOOTH_ZOOM_DURATION, self)
        zoom_time_line.setUpdateInterval(SMOOTH_ZOOM_UPDATE_INTERVAL)
        zoom_time_line.valueChanged.connect(partial(self.zoom_view, zoom))
        zoom_time_line.finished.connect(self.zoom_finished)
        zoom_time_line.start()

    def zoom_view(self, zoom):
        old_pos = self.view.mapToScene(zoom.pos)
        self.view.scale(zoom.factor, zoom.factor)
        new_pos = self.view.mapToScene(zoom.pos)

        # Move the scene's view to old position
        delta = new_pos - old_pos
        self.view.translate(delta.x(), delta.y())


class ViewerImageItem(QGraphicsItem):
    def __init__(self):
        super().__init__()

        self.layers = []

    def boundingRect(self):
        if self.layers:
            image = self.layers[0].displayed_image
            return QRectF(image.rect())
        else:
            return QRectF()

    def add_layer(self, layer: ImageViewerLayer):
        self.layers.append(layer)
        # Calling update() several times normally results in just one paintEvent() call.
        # See QWidget::update() documentation.
        layer.updated.connect(self.update)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for layer in self.layers:
            if layer.image is not None and layer.visible:
                painter.setOpacity(layer.opacity)
                painter.drawImage(0, 0, layer.displayed_image)


class GraphicsView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.scene_center = None
        view_smooth_zoom = _ViewSmoothZoom(self, self)
        view_smooth_zoom.zoom_finished.connect(self.on_zoom_finished)
        self.viewport().installEventFilter(view_smooth_zoom)

        scene = QGraphicsScene()
        # scene.setSceneRect(-300, -300, 600, 600)

        self.pixmap_item = ViewerImageItem()
        #%self.pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        scene.addItem(self.pixmap_item)

        self.setScene(scene)

        # self.setBackgroundBrush(QBrush(Qt.black))

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

    def mousePressEvent(self, event: QMouseEvent):
        pos = self.pixmap_item.mapFromScene(self.mapToScene(event.pos()))
        item = QGraphicsEllipseItem(pos.x() - 5, pos.y() - 5, 10, 10, self.pixmap_item)
        # self.scene().addItem(QGraphicsEllipseItem(pos.x() - 5, pos.y() - 5, 10, 10, self.pixmap_item))

    def on_zoom_finished(self):
        self.scene_center = self.mapToScene(self.viewport().rect().center())

    def center_image(self):
        pixmap_size = self.pixmap_item.boundingRect().size()
        margins_size = pixmap_size
        top_left_point = QPointF(self.pixmap_item.pos() - QPointF(margins_size.width(), margins_size.height()))
        size = QSizeF(2 * margins_size + pixmap_size)
        self.setSceneRect(QRectF(top_left_point, size))
        self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        # self.centerOn(self.pixmap_item)

    def showEvent(self, event: QShowEvent):
        self.center_image()

    def resizeEvent(self, e):
        '''
        if not self.scene_center:
            self.on_zoom_finished()
        print('RESIZE', self.scene_center)
        self.centerOn(self.scene_center)
        '''
        self.center_image()

        super().resizeEvent(e)


class FlatImageViewer(DataViewer):
    before_image_changed = Signal()
    image_changed = Signal()
    colormap_active_class_changed = Signal(int)

    def __init__(self, image: FlatImage = None):
        super().__init__(image)

        self.graphics_view = GraphicsView()
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)

        grid_layout.addWidget(self.graphics_view)
        self.setLayout(grid_layout)

#%        self.main_window = main_window  #%! Temp
        print('shape:', image.array.shape)
        self.image_layer = ImageViewerLayer('Image', image)
        #%self.mask_layer = ImageViewerLayer('Mask')

        #%self.layers = [self.image_layer] #%, self.mask_layer]
        #%self.graphics_view.pixmap_item.layers = self.layers
        self.graphics_view.pixmap_item.add_layer(self.image_layer)
        # self.pixmap_item.update()

        # self.layers = {self.image_layer.id: self.image_layer,
        #                self.mask_layer.id: self.mask_layer}

        self.initial_mask = None

        self.colormap = Colormap()
#        self.colormap.changed.connect(self.update_scaled_combined_image)
        self.colormap.active_color_class_changed.connect(self.colormap_active_class_changed)

        self.combined_qimage = None
        self.scaled_combined_qimage = None
        # self.image_scale = None

        self.setMinimumSize(100, 100)
        # self.setAlignment(Qt.AlignTop)

        # self.setAcceptDrops(True)

        # self.view_mode = ViewMode.FILE
        self.image_path = '' #tests/start_image.png'
        self.mask_path = ''
        self.view_path = ''
        self.images_path = ''
        self.masks_path = ''
        self.dir_image_index = 0
        self.dir_images = []

        self.image_view = False

        #self.drop_file('test_data/test_image.png')
        # self.tool_interactor = SmartBrushToolInteractor(self)
        # self.tool_interactor = GrabCutToolInteractor(self)
        # self.tool_interactor = GrabCutBrushToolInteractor(self)
        # self.installEventFilter(self.tool_interactor)

        # self.setFocusPolicy(Qt.StrongFocus)  # for key events

    @property
    def layers(self):
        return self.graphics_view.pixmap_item.layers

    def add_layer(self, name, image: FlatImage = None, colormap: Colormap = None):
        self.graphics_view.pixmap_item.add_layer(ImageViewerLayer(name, image, colormap))

    def remove_layer(self, layer):
        self.layers.remove(layer)

    def toogle_mask_visibility(self):
        self.mask_layer.visible = not self.mask_layer.visible
        self.update_scaled_combined_image()

    def toogle_image_view(self):
        self.image_view = not self.image_view
        self.update_scaled_combined_image()

    '''
    def image(self):
        return self.image_layer.image
    def mask(self):
        return self.mask_layer.image
    '''

    @property
    def image(self):
        return self.image_layer.image

    @property
    def mask(self):
        return self.mask_layer.image

    def has_image(self):
        return self.image() is not None

    def is_over_image(self, pos):
        pos = self.mapToScene(pos)
        return 0 <= pos.x() <= self.scaled_combined_qimage.width() \
            and 0 <= pos.y() <= self.scaled_combined_qimage.height()
        # return pos.x() <= self.scaled_combined_qimage.width() and pos.y() <= self.scaled_combined_qimage.height()

    def pos_to_image_coords(self, pos):
        # pixmap_pos = self.pixmap_item.mapFromScene(self.mapToScene(pos))
        # return [round(pixmap_pos.y()), round(pixmap_pos.x())]

        pos = self.mapToScene(pos)
        return [round(pos.y()), round(pos.x())]

    '''
    def dragEnterEvent(self, e):
        print('ddd')
        path = e.mimeData().urls()[0].toLocalFile()
        if not os.path.exists(path):
            e.ignore()
            return
        if os.path.isdir(path) or path.endswith('.png') or path.endswith('.jpg'):
            e.accept()
        else:
            e.ignore()
    def dropEvent(self, e):
        path = e.mimeData().urls()[0].toLocalFile()
        self.drop_file(path)
    '''

    def drop_file(self, path):
        self.actions_before_image_changed()

        if os.path.isdir(path) and os.path.exists(os.path.join(path, 'image')):
            self.view_path = path
            self.images_path = os.path.join(self.view_path, 'image')
            self.masks_path = os.path.join(self.view_path, 'mask')

            self.dir_images = sorted(os.listdir(self.images_path))
            self.dir_image_index = 0

        elif path.endswith('.png') or path.endswith('.jpg'):
            self.images_path = os.path.dirname(path)
            self.view_path = os.path.dirname(self.images_path)
            self.masks_path = os.path.join(self.view_path, 'mask')

            self.dir_images = sorted(os.listdir(self.images_path))
            self.dir_image_index = self.dir_images.index(os.path.basename(path))

        else:
            return

        if not self.dir_images:
            return

        self.load_image_in_dir_by_index(self.dir_image_index)

    def save_current_mask(self):
        if self.mask() is None or not os.path.exists(self.masks_path):
            return

        mask_data = self.mask().data
        if (mask_data != self.initial_mask.data).any():
            print('save', self.mask_path)

            binary_mask = np.zeros(mask_data.shape[:2], np.uint8)
            binary_mask[np.where((mask_data == settings.MASK_COLOR).all(axis=2))] = 255

            # cv2.imwrite(self.mask_path, binary_mask)
            imsave(self.mask_path, binary_mask)

    def save_current_image(self):
        if self.image() is None:
            return

        save_folder = os.path.join(self.view_path, 'image-edited')
        if not os.path.exists(save_folder):
            return

        save_path = os.path.join(save_folder, os.path.basename(self.image_path))
        imsave(save_path, self.image().data[:, :, :3])

    def actions_before_image_changed(self):
        self.save_current_mask()
        # self.save_current_image()
        self.before_image_changed.emit()

    def change_image_in_dir_by_index(self, index):
        self.actions_before_image_changed()
        self.load_image_in_dir_by_index(index)

    def load_image_in_dir_by_index(self, index):
        self.dir_image_index = index % len(self.dir_images)
        file_name = self.dir_images[self.dir_image_index]
        image_path = os.path.join(self.images_path, file_name)
        mask_path = os.path.join(self.masks_path, file_name)
        self.load_image(image_path, mask_path)

    def show_next_image(self):
        # Load next image and mask in folder
        self.change_image_in_dir_by_index(self.dir_image_index + 1)

    def show_previous_image(self):
        # Load previous image and mask in folder
        self.change_image_in_dir_by_index(self.dir_image_index - 1)

    def load_image(self, image_path, mask_path=None):
        if not (os.path.exists(image_path) and (image_path.endswith('.png') or image_path.endswith('.jpg'))):
            return
        print('--- Load:', image_path, '---')
        self.image_path = image_path
#%        self.main_window.setWindowTitle(os.path.basename(self.image_path))
        self.mask_path = mask_path

        self.image_layer.image = FlatImage(imread(self.image_path))
        # self.image_layer.image.data = resize(self.image_layer.image.data, (512, 512), anti_aliasing=True)
        # print('s', self.image().data.shape)
        image_utils.print_image_info(self.image().data, 'original')
        self.image().data = image_utils.converted_to_normalized_uint8(self.image().data)
        self.image().data = image_utils.converted_to_rgba(self.image().data)
        image_utils.print_image_info(self.image().data, 'converted')

        if os.path.exists(mask_path):
            print('mask', mask_path)
            mask = imread(mask_path)
            image_utils.print_image_info(mask, 'mask original')
            # If mask is greyscale then convert to binary
            if len(np.unique(mask)) > 2:
                mask[mask >= 127] = 255
                mask[mask < 127] = 0
            mask = image_utils.converted_to_normalized_uint8(mask)
            mask = image_utils.converted_to_rgba_mask(mask)
            # Paint the mask (change color)
            mask[np.where((mask != [0, 0, 0, 0]).all(axis=2))] = settings.MASK_COLOR
            image_utils.print_image_info(mask, 'mask converted')
        else:
#            mask = np.zeros(self.image().data.shape, np.uint8)
            mask = np.full((self.image().data.shape[0], self.image().data.shape[1]), settings.NO_MASK_CLASS, np.uint8)
        self.mask_layer.image = FlatImage(mask)
        self.initial_mask = FlatImage(np.copy(mask))

        self.update_scaled_combined_image()
        self.center_image()
        self.image_changed.emit()

    '''
    def update_scaled_combined_image(self):
        if not self.has_image():
            return
        self.pixmap_item.update()
        self.combined_qimage = image_utils.numpy_rgba_image_to_qimage(self.layers[0].image.data)
        if not self.image_view:
            painter = QPainter(self.combined_qimage)
            for i in range(1, len(self.layers)):
                layer = self.layers[i]
                if layer.image is not None and layer.visible:
                    painter.setOpacity(layer.opacity)
                    rgba_layer_image_data = self.colormap.colored_premultiplied_image(layer.image.data)
                    painter.drawImage(0, 0, image_utils.numpy_rgba_image_to_qimage(rgba_layer_image_data))
            painter.end()
        # self.scaled_combined_qimage = self.combined_qimage.scaled(self.width(), self.height(),
        #                                                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # self.image_scale = self.scaled_combined_qimage.width() / self.combined_qimage.width()
        # self.pixmap_item.setPixmap(QPixmap(self.scaled_combined_qimage))
        self.pixmap_item.setPixmap(QPixmap(self.combined_qimage))
    '''
