from __future__ import annotations

import sys
from pathlib import Path


class DataFileProvider:
    _BASE_DATA_DIRS = ('configs',)
    _DATA_DIRS = ()

    _FROZEN_DATA_DIR_NAME = 'data'

    @classmethod
    def data_dirs(cls) -> tuple:
        return tuple(set(cls._BASE_DATA_DIRS).union(set(cls._DATA_DIRS)))

    @classmethod
    def module_dir(cls) -> Path:
        return Path(sys.modules[cls.__module__].__file__).parent.resolve()

    @classmethod
    def frozen_rel_data_path(cls, *rel_path_parts) -> Path:
        """Returns path relative to *.exe."""
        return cls._FROZEN_DATA_DIR_NAME / Path(sys.modules[cls.__module__].__package__).joinpath(*rel_path_parts)

    @classmethod
    def frozen_absolute_data_path(cls, *rel_path_parts) -> Path:
        return Path(sys.executable).parent.resolve().joinpath(cls.frozen_rel_data_path(*rel_path_parts))

    @classmethod
    def absolute_data_path(cls, *rel_path_parts) -> Path:
        return cls.module_dir().joinpath(*rel_path_parts)

    @classmethod
    def data_path(cls, *rel_path_parts) -> Path:
        if getattr(sys, 'frozen', False):
            # The application is frozen into *.exe
            return cls.frozen_absolute_data_path(*rel_path_parts)
        else:
            # The application is not frozen
            return cls.absolute_data_path(*rel_path_parts)

    @classmethod
    def frozen_rel_data_dir_by_absolute(cls) -> dict[Path, Path]:
        frozen_rel_data_dir_by_absolute = {}
        for data_dir in cls.data_dirs():
            absolute_data_dir = cls.absolute_data_path(data_dir)
            if not absolute_data_dir.exists():
                continue

            frozen_rel_data_dir = cls.frozen_rel_data_path(data_dir)
            frozen_rel_data_dir_by_absolute[absolute_data_dir] = frozen_rel_data_dir
        return frozen_rel_data_dir_by_absolute
