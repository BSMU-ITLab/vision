from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from bsmu.vision.core.freeze import is_app_frozen
from bsmu.vision.core.utils.package import PackageUtils

if TYPE_CHECKING:
    from bsmu.vision.core.utils.package import PackageInfo


class DataFileProvider:
    _DATA_DIRS: tuple[str] = ()

    _FROZEN_DATA_DIR_NAME: str = 'data'
    _FROZEN_RESOURCES_DIR_NAME: str = 'resources'

    _FIRST_REGULAR_PACKAGE_INFO: PackageInfo | None = None

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Initialize `cls._FIRST_REGULAR_PACKAGE_INFO` to None for each subclass
        # to ensure each one has its own attribute that can be set independently.
        cls._FIRST_REGULAR_PACKAGE_INFO = None

    @classmethod
    def data_dirs(cls) -> tuple[str]:
        return cls._DATA_DIRS

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
    def frozen_rel_data_dir(cls) -> Path:
        return Path(cls._FROZEN_DATA_DIR_NAME)

    @classmethod
    def frozen_rel_resources_dir(cls) -> Path:
        return cls.frozen_rel_data_dir() / cls._FROZEN_RESOURCES_DIR_NAME

    @classmethod
    def frozen_exe_dir(cls) -> Path:
        return Path(sys.executable).parent.resolve()

    @classmethod
    def frozen_absolute_data_dir(cls) -> Path:
        return cls.frozen_exe_dir() / cls.frozen_rel_data_dir()

    @classmethod
    def frozen_absolute_resources_dir(cls) -> Path:
        return cls.frozen_exe_dir() / cls.frozen_rel_resources_dir()

    @classmethod
    def module_dir(cls) -> Path:
        module = sys.modules.get(cls.__module__)
        assert module is not None, \
            f'{cls.__module__} module is not found in sys.modules. Cannot get module directory for {cls}.'
        return Path(module.__file__).parent.resolve()

    @classmethod
    def frozen_rel_resources_path(cls, *rel_path_parts) -> Path:
        """Returns path relative to *.exe."""
        module = sys.modules.get(cls.__module__)
        assert module is not None, \
            f'{cls.__module__} module is not found in sys.modules. ' \
            f'Cannot get frozen relative resources path for {rel_path_parts}.'
        package = module.__package__
        assert package is not None, \
            f'{module} has no package. Cannot get frozen relative resources path for {rel_path_parts}.'
        return (cls.frozen_rel_resources_dir() / package).joinpath(*rel_path_parts)

    @classmethod
    def frozen_absolute_resources_path(cls, *rel_path_parts) -> Path:
        return cls.frozen_exe_dir().joinpath(cls.frozen_rel_resources_path(*rel_path_parts))

    @classmethod
    def unfrozen_data_path(cls, *rel_path_parts) -> Path:
        return cls.module_dir().joinpath(*rel_path_parts)

    @classmethod
    def data_path(cls, *rel_path_parts) -> Path:
        if is_app_frozen():
            return cls.frozen_absolute_resources_path(*rel_path_parts)
        else:
            return cls.unfrozen_data_path(*rel_path_parts)

    @classmethod
    def unfrozen_to_frozen_rel_data_path(cls) -> dict[Path, Path]:
        unfrozen_to_frozen_rel_data_path = {}
        for data_dir in cls.data_dirs():
            unfrozen_data_path = cls.unfrozen_data_path(data_dir)
            if not unfrozen_data_path.exists():
                continue

            frozen_rel_data_path = cls.frozen_rel_resources_path(data_dir)
            unfrozen_to_frozen_rel_data_path[unfrozen_data_path] = frozen_rel_data_path
        return unfrozen_to_frozen_rel_data_path
