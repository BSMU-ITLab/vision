from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from bsmu.vision.core.freeze import is_app_frozen
from bsmu.vision.core.utils.package import PackageUtils

if TYPE_CHECKING:
    from bsmu.vision.core.utils.package import PackageInfo


class DataFileProvider:
    _BASE_DATA_DIRS = ('configs',)
    _DATA_DIRS = ()

    _FROZEN_DATA_DIR_NAME = 'data'

    _FIRST_REGULAR_PACKAGE_INFO: PackageInfo | None = None

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Initialize `cls._FIRST_REGULAR_PACKAGE_INFO` to None for each subclass
        # to ensure each one has its own attribute that can be set independently.
        cls._FIRST_REGULAR_PACKAGE_INFO = None

    @classmethod
    def first_regular_package_info(cls) -> PackageInfo:
        if cls._FIRST_REGULAR_PACKAGE_INFO is None:
            try:
                cls._FIRST_REGULAR_PACKAGE_INFO = PackageUtils.first_regular_package_info(cls)
            except RuntimeError as e:
                raise RuntimeError(
                    f'Error in {cls.__name__}. '
                    f'DataFileProvider classes should not be placed in the "__main__" module. '
                    f'Please move it to a module other than "__main__".'
                ) from e
        return cls._FIRST_REGULAR_PACKAGE_INFO

    @classmethod
    def frozen_data_dir_name(cls) -> str:
        return cls._FROZEN_DATA_DIR_NAME

    @classmethod
    def data_dirs(cls) -> tuple:
        return tuple(set(cls._BASE_DATA_DIRS).union(set(cls._DATA_DIRS)))

    @classmethod
    def module_dir(cls) -> Path:
        module = sys.modules.get(cls.__module__)
        assert module is not None, \
            f'{cls.__module__} module is not found in sys.modules. Cannot get module directory for {cls}.'
        return Path(module.__file__).parent.resolve()

    @classmethod
    def frozen_rel_data_path(cls, *rel_path_parts) -> Path:
        """Returns path relative to *.exe."""
        module = sys.modules.get(cls.__module__)
        assert module is not None, \
            f'{cls.__module__} module is not found in sys.modules. ' \
            f'Cannot get frozen relative data path for {rel_path_parts}.'
        package = module.__package__
        assert package is not None, \
            f'{module} has no package. Cannot get frozen relative data path for {rel_path_parts}.'
        return cls._FROZEN_DATA_DIR_NAME / Path(package).joinpath(*rel_path_parts)

    @classmethod
    def frozen_absolute_data_path(cls, *rel_path_parts) -> Path:
        return Path(sys.executable).parent.resolve().joinpath(cls.frozen_rel_data_path(*rel_path_parts))

    @classmethod
    def absolute_data_path(cls, *rel_path_parts) -> Path:
        return cls.module_dir().joinpath(*rel_path_parts)

    @classmethod
    def data_path(cls, *rel_path_parts) -> Path:
        if is_app_frozen():
            return cls.frozen_absolute_data_path(*rel_path_parts)
        else:
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
