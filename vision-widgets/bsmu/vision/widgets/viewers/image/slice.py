from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer


class VolumeSliceImageViewer(DataViewer):
    def __init__(self, image: VolumeImage = None, zoomable: bool = True):
        super().__init__(image)

        self._layered_image_viewer = LayeredImageViewer(image[:, :, 200], zoomable)
