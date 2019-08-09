from bsmu.vision_core.data import Data


class Image(Data):
    def __init__(self, array=None, path=None):
        super().__init__(path)

        self.array = array


class FlatImage(Image):
    def __init__(self, array=None, path=None):
        super().__init__(array, path)


class VolumeImage(Image):
    def __init__(self, array=None, path=None):
        super().__init__(array, path)
