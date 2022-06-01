from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import List

from cx_Freeze import setup, Executable

import bsmu.vision.plugins
from bsmu.vision.core.data_file import DataFileProvider


# see: https://packaging.python.org/guides/creating-and-discovering-plugins/#using-namespace-packages
def iter_namespace_package_modules(namespace_package: ModuleType):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(namespace_package.__path__, namespace_package.__name__ + ".")


def find_modules_of_package_recursively(package: ModuleType, indent: int = 0):
    indent_str = indent * '\t'
    print(f'{indent_str}package:', package)
    for finder, name, ispkg in iter_namespace_package_modules(package):
        # print('Try to import:', name)  # Use this print to find current package or module with errors during import
        module_or_package = importlib.import_module(name)
        if ispkg:
            yield from find_modules_of_package_recursively(module_or_package, indent + 1)
        else:
            indent_str = (indent + 1) * '\t'
            print(f'{indent_str}module:', module_or_package)
            yield module_or_package


def find_modules_of_packages_recursively(packages: List[ModuleType], indent: int = 0):
    for package in packages:
        yield from find_modules_of_package_recursively(package, indent)


def generate_list_of_data_file_tuples(packages_with_data: List[ModuleType]):
    """
    :param packages_with_data: packages to search DataFileProvider classes
    :return: e.g. list of such tuples:
    ('full-path/vision-app/bsmu/vision/app/App.conf.yaml', 'data/bsmu.vision.app/configs/App.conf.yaml')
    full signature is:
    [('full path to the data file or dir', 'relative path to the data file or dir in the build folder'), ...]
    """
    # Use dictionary to remove duplicate values
    destination_data_path_by_absolute = {}
    for module in find_modules_of_packages_recursively(packages_with_data):
        class_name_value_pairs = inspect.getmembers(module, inspect.isclass)
        for cls_name, cls in class_name_value_pairs:
            # Skip classes, which were imported
            if cls.__module__ != module.__name__:
                continue

            if not issubclass(cls, DataFileProvider):
                continue

            for absolute_data_dir, frozen_rel_data_dir in cls.frozen_rel_data_dir_by_absolute().items():
                destination_data_path_by_absolute[absolute_data_dir] = frozen_rel_data_dir

    # Convert |destination_data_path_by_absolute| dict to list of tuples
    data_file_absolute_path_and_destination_tuples = \
        [(str(absolute_data_path), str(frozen_rel_data_path))
         for absolute_data_path, frozen_rel_data_path in destination_data_path_by_absolute.items()]

    return data_file_absolute_path_and_destination_tuples


class AppBuilder:
    _BUILD_DIR_NAME = 'build'
    _DIST_DIR_NAME = 'dist'

    _BASE_BUILD_EXE_PACKAGES = [
        'scipy.fftpack', 'scipy.ndimage',
        'skimage.io', 'skimage.util', 'skimage.color',
        'numpy.core',
        'ruamel.yaml',
        'bsmu.vision.app',
        'bsmu.vision.core',
        'bsmu.vision.dnn',
        'bsmu.vision.plugins',
        'bsmu.vision.widgets',
        'imageio',
    ]

    def __init__(
            self,
            file_dir: Path = Path(__file__).parent,
            script_path_relative_to_file_dir: Path = Path('src/bsmu/vision/app/__main__.py'),
            build_dir: Path | None = None,
            dist_dir: Path | None = None,

            app_name: str = 'Vision',
            app_version: str = '1.0.0',
            app_description: str = 'Base application for image visualization and processing '
                                   'that is easily extensible with plugins.',
            app_base: str | None = 'Win32GUI',  # Use None for a console application
            # (or to display GUI and console windows)
            icon_path_relative_to_file_dir: Path | None = None,

            add_packages: List[str] | None = None,
            packages_with_data: List[ModuleType] | None = None,
            add_packages_with_data: List[ModuleType] | None = None,

            build_exe_options: dict | None = None,
            install_exe_options: dict | None = None,
            bdist_msi_options: dict | None = None,
    ):
        self._file_dir = file_dir
        self._script_path_relative_to_file_dir = script_path_relative_to_file_dir
        self._build_name = f'{app_name.replace(" ", "")}-{app_version}'
        console_suffix = '-c' if app_base is None else ''
        self._build_name_with_console_suffix = self._build_name + console_suffix
        self._build_dir = self._file_dir / self._BUILD_DIR_NAME / self._build_name_with_console_suffix \
            if build_dir is None else build_dir
        self._dist_dir = self._file_dir / self._DIST_DIR_NAME if dist_dir is None else dist_dir

        self._app_name = app_name
        self._app_version = app_version
        self._app_description = app_description
        self._app_base = app_base
        if icon_path_relative_to_file_dir is None:
            self._icon_path = Path(__file__).parent / 'images/icons/vision.ico'
        else:
            self._icon_path = self._file_dir / icon_path_relative_to_file_dir

        if build_exe_options is None:
            default_packages = self._BASE_BUILD_EXE_PACKAGES
            if add_packages is not None:
                default_packages += add_packages

            if packages_with_data is None:
                default_packages_with_data = [bsmu.vision.app, bsmu.vision.plugins]
                if add_packages_with_data is not None:
                    default_packages_with_data += add_packages_with_data
                packages_with_data = default_packages_with_data

            self._build_exe_options = self._generate_default_build_exe_options(
                default_packages, packages_with_data)
        else:
            self._build_exe_options = build_exe_options

        self._install_exe_options = self._generate_default_install_exe_options() \
            if install_exe_options is None else install_exe_options
        self._bdist_msi_options = self._generate_default_bdist_msi_options() \
            if bdist_msi_options is None else bdist_msi_options

    def build(self):
        setup(
            name=self._app_name,
            version=self._app_version,
            description=self._app_description,
            options={
                'build_exe': self._build_exe_options,
                'install_exe': self._install_exe_options,
                'bdist_msi': self._bdist_msi_options,
            },
            executables=[Executable(
                self._file_dir / self._script_path_relative_to_file_dir,
                base=self._app_base,
                target_name=self._build_name_with_console_suffix,
                shortcut_name=self._app_name,
                shortcut_dir='DesktopFolder',
                icon=self._icon_path,
            )]
        )

    def _generate_default_build_exe_options(
            self,
            packages: List[str],
            packages_with_data: List[ModuleType]
    ) -> dict:
        list_of_data_file_tuples = generate_list_of_data_file_tuples(packages_with_data)
        frozen_rel_data_paths = [data_file_tuple[1] for data_file_tuple in list_of_data_file_tuples]
        data_modules_to_exclude = []
        for frozen_rel_data_path in frozen_rel_data_paths:
            data_module_to_exclude = frozen_rel_data_path.replace('\\', '.')
            data_module_to_exclude = data_module_to_exclude[len(DataFileProvider.frozen_data_dir_name()) + len('.'):]
            data_modules_to_exclude.append(data_module_to_exclude)
        print('Data modules to exclude:', data_modules_to_exclude)

        excludes = ['tkinter', 'scipy.spatial.cKDTree'] + data_modules_to_exclude
        return {
            'build_exe': self._build_dir,
            'packages': packages,
            'excludes': excludes,
            'includes': ['numpy', 'scipy.sparse.csgraph._validation'],
            'include_files': list_of_data_file_tuples,
        }

    def _generate_default_install_exe_options(self) -> dict:
        return {
            'build_dir': self._build_dir,
        }

    def _generate_default_bdist_msi_options(self) -> dict:
        return {
            'bdist_dir': self._dist_dir / 'temp',
            'dist_dir': str(self._dist_dir),
        }
