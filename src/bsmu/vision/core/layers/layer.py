from __future__ import annotations

import warnings
from pathlib import Path
from typing import Generic, TypeVar, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.bbox import BBox
from bsmu.vision.core.data import Data
from bsmu.vision.core.data.raster import Raster
from bsmu.vision.core.data.vector import Vector
from bsmu.vision.core.visibility import Visibility

if TYPE_CHECKING:
    from typing import Optional

    import numpy.typing as npt

    from bsmu.vision.core.palette import Palette

DataT = TypeVar('DataT', bound=Data)


class Layer(QObject, Generic[DataT]):
    _max_id: int = 0

    data_about_to_change = Signal(Data, Data)
    data_changed = Signal(Data)
    path_changed = Signal(Path)
    extension_changed = Signal(str)
    visible_changed = Signal(bool)
    opacity_changed = Signal(float)

    data_path_changed = Signal(Path)

    def __init__(
            self,
            data: DataT | None = None,
            name: str = '',
            path: Path | None = None,
            visibility: Visibility | None = None,
            parent: QObject | None = None,
    ):
        """
        :param path: Layer path used to iterate over data files.
        """
        super().__init__(parent)

        self._id: int = Layer._max_id
        Layer._max_id += 1
        self._name: str = name if name else f'Layer {self._id}'

        self._path: Path | None = path
        self._extension: str | None = None

        self._visibility: Visibility = Visibility() if visibility is None else visibility

        self._data: DataT | None = None

        # NOTE: `self.data = data` triggers _data_about_to_change() and _data_changed().
        # These methods may be overridden in subclasses.
        # Therefore, subclasses must initialize all their instance
        # attributes *before* calling super().__init__(),
        # to ensure they are ready when these hooks execute.
        self.data = data

    @property
    def data(self) -> DataT | None:
        return self._data

    @data.setter
    def data(self, value: DataT | None):
        if self._data == value:
            return

        self.data_about_to_change.emit(self._data, value)
        self._data_about_to_change(value)

        old_data_path = self.data_path

        if self._data is not None:
            self._data.path_changed.disconnect(self._on_data_path_changed)

        self._data = value

        if self._data is not None:
            self._data.path_changed.connect(self._on_data_path_changed)

        new_data_path = self.data_path
        if old_data_path != new_data_path:
            self._on_data_path_changed(self.data_path)

        self._data_changed()
        self.data_changed.emit(self._data)

    @property
    def name(self) -> str:
        return self._name

    @property
    def path(self) -> Path | None:
        return self._path

    @path.setter
    def path(self, value: Path | None):
        if self._path != value:
            self._path = value
            self.path_changed.emit(self._path)

    @property
    def visibility(self) -> Visibility:
        return self._visibility

    @property
    def visible(self) -> bool:
        return self._visibility.visible

    @visible.setter
    def visible(self, value: bool):
        if self._visibility.visible != value:
            self._visibility.visible = value
            self.visible_changed.emit(self.visible)

    @property
    def opacity(self) -> float:
        return self._visibility.opacity

    @opacity.setter
    def opacity(self, value: float):
        if not (0.0 <= value <= 1.0):
            raise ValueError('Opacity must be between 0.0 and 1.0')
        if self._visibility.opacity != value:
            self._visibility.opacity = value
            self.opacity_changed.emit(self.opacity)

    @property
    def extension(self) -> str | None:
        """ Extension of its last data file that is not None. """
        return self._extension

    @extension.setter
    def extension(self, value: str | None):
        if self._extension != value:
            self._extension = value
            self.extension_changed.emit(self._extension)

    @property
    def data_path(self) -> Path | None:
        return self._data.path if self._data is not None else None

    @property
    def data_path_name(self) -> str:
        return self.data_path.name if self.data_path is not None else ''

    def _data_about_to_change(self, new_data: DataT | None):
        pass

    def _data_changed(self):
        pass

    def _on_data_path_changed(self, path: Path | None):
        self._update_extension()
        self.data_path_changed.emit(path)

    def _update_extension(self):
        if self.data_path is not None:
            self.extension = self._data.path.suffix


class RasterLayer(Layer[Raster]):
    image_shape_changed = Signal(object, object)  # TODO: rename into raster_shape_changed
    image_pixels_modified = Signal(BBox)  # TODO: rename into raster_pixels_modified

    def __init__(
            self,
            data: Raster | None = None,
            name: str = '',
            path: Path | None = None,
            visibility: Visibility | None = None,
            parent: QObject | None = None,
    ):
        # Cache the palette because raster data may be None,
        # in which case self.data.palette is inaccessible.
        self._palette: Palette | None = None

        super().__init__(data, name, path, visibility, parent)

    @property
    def palette(self) -> Palette | None:
        return self._palette

    @property
    def image_path(self) -> Path | None:
        warnings.warn('`image_path` is deprecated; use `data_path` instead.', DeprecationWarning, stacklevel=2)
        return self.data_path

    @property
    def raster_palette(self) -> Palette | None:
        return self.data.palette if self.data is not None else None

    @property
    def image_palette(self) -> Palette | None:
        warnings.warn('`image_palette` is deprecated; use `raster_palette` instead.', DeprecationWarning, stacklevel=2)
        return self.raster_palette

    @property
    def raster_pixels(self) -> Optional[npt.NDArray]:
        return self.data.pixels if self.data is not None else None

    @property
    def image_pixels(self) -> Optional[npt.NDArray]:
        warnings.warn('`image_pixels` is deprecated; use `raster_pixels` instead.', DeprecationWarning, stacklevel=2)
        return self.raster_pixels

    @property
    def image_path_name(self) -> str:
        warnings.warn('`image_path_name` is deprecated; use `data_path_name` instead.', DeprecationWarning, stacklevel=2)
        return self.data_path_name

    @property
    def image(self) -> Raster | None:
        warnings.warn('`image` is deprecated; use `data` instead.', DeprecationWarning, stacklevel=2)
        return self.data

    @image.setter
    def image(self, value: Raster | None):
        warnings.warn('`image` is deprecated; use `data` instead.', DeprecationWarning, stacklevel=2)
        self.data = value

    def _data_about_to_change(self, new_data: Raster | None):
        if self.data is not None:
            self.data.pixels_modified.disconnect(self.image_pixels_modified)
            self.data.shape_changed.disconnect(self.image_shape_changed)

    def _data_changed(self):
        if self.data is not None:
            self._palette = self.data.palette
            self.data.pixels_modified.connect(self.image_pixels_modified)
            self.data.shape_changed.connect(self.image_shape_changed)

    @property
    def is_indexed(self) -> bool:
        return self._palette is not None

    @property
    def is_raster_pixels_valid(self) -> bool:
        return self.data is not None and self.data.is_pixels_valid

    @property
    def is_image_pixels_valid(self) -> bool:
        warnings.warn('`is_image_pixels_valid` is deprecated; use `is_raster_pixels_valid` instead.', DeprecationWarning, stacklevel=2)
        return self.is_raster_pixels_valid


class VectorLayer(Layer[Vector]):
    ...
