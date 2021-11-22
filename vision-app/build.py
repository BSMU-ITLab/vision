# To build *.exe use the next command in the terminal:
#   (vision) D:\Projects\vision>   python vision-app/build.py build

# To create an msi-installer:
#   (vision) D:\Projects\vision>   python vision-app/build.py bdist_msi

# To build app, install all required packages using pip
# For local dev packages (e.g. bsmu.vision.plugins) use:
#   pip install -e /path/to/dir/with/setup.py
# Or add them to the system path, e.g. using:
#   sys.path.append('D:\\Projects\\vision\\vision-plugins')


from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from types import ModuleType
from typing import List

from cx_Freeze import setup, Executable

import bsmu.vision.app
import bsmu.vision.core
import bsmu.vision.dnn
import bsmu.vision.plugins
import bsmu.vision.widgets
from bsmu.vision.core.data_file import DataFileProvider

FILE_DIR = Path(__file__).parent
BUILD_DIR = FILE_DIR / 'build'
DIST_DIR = FILE_DIR / 'dist'


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


# Dependencies are automatically detected, but it might need fine tuning
build_exe_options = {
    'packages': [
        'scipy.fftpack', 'scipy.ndimage',
        'skimage.io', 'skimage.util', 'skimage.color',
        'numpy.core',
        'ruamel.yaml',
        'bsmu.vision.app',
        'bsmu.vision.core',
        'bsmu.vision.dnn',
        'bsmu.vision.plugins',
        'bsmu.vision.widgets',
    ],
    'excludes': ['tkinter', 'scipy.spatial.cKDTree'],  # to fix the current bug
    'includes': ['numpy', 'scipy.sparse.csgraph._validation'],
    'include_files': generate_list_of_data_file_tuples([bsmu.vision.app, bsmu.vision.plugins]),
    'build_exe': BUILD_DIR,
}

install_exe_options = {
    'build_dir': BUILD_DIR,
}

bdist_msi_options = {
    'bdist_dir': DIST_DIR / 'temp',
    'dist_dir': str(DIST_DIR),
}

# GUI applications require a different base on Windows (the default is for a console application).
app_base = 'Win32GUI' if sys.platform == 'win32' else None
print('app_base:', app_base)

setup(
    name='Vision',
    version='0.1.0',
    description='Base application for extension by plugins',
    options={
        'build_exe': build_exe_options,
        'install_exe': install_exe_options,
        'bdist_msi': bdist_msi_options,
    },
    executables=[Executable(
        FILE_DIR / 'bsmu/vision/app/main.py',
        base=app_base,
        shortcut_name='Bone Age Analyzer',
        shortcut_dir='DesktopFolder',
    )]
)
