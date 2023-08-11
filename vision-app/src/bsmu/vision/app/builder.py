from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from types import ModuleType
from typing import List

from cx_Freeze import setup, Executable

import bsmu.vision.app
import bsmu.vision.plugins
from bsmu.vision.core.data_file import DataFileProvider


def generate_list_of_data_file_tuples_in_subprocess(packages_with_data: List[ModuleType]) -> list[tuple[str, str]]:
    """
    Get |list_of_data_file_tuples| using subprocess to fix strange crash during build.exe step.
    The crash happens, when onnxruntime was previously imported.
    (Everything worked well with onnxruntime-gpu 1.10.0, but with onnxruntime-gpu 1.14.1 crash happens.)
    Subprocess allows to separate importlib.import_module calls and build.exe stage. So no crash happens.
    """
    package_names = [package.__name__ for package in packages_with_data]
    kwargs = {'package_names': package_names}
    out = subprocess.check_output(
        ['python', Path(__file__).parent / 'builder_helper.py', str(kwargs)])
    out = out.decode('utf-8')
    # Filter out empty strings after split
    last_printed_output_str = list(filter(None, out.split('\n')))[-1]
    last_printed_output_dict = ast.literal_eval(last_printed_output_str)
    list_of_data_file_tuples = last_printed_output_dict['list_of_data_file_tuples']
    return list_of_data_file_tuples


class AppBuilder:
    _BUILD_DIR_NAME = 'build'
    _DIST_DIR_NAME = 'dist'

    _BASE_BUILD_EXE_PACKAGES = [
        'imageio',
        'numpy.core',
        'ruamel.yaml',
        'scipy.fftpack', 'scipy.ndimage',
        'skimage.color', 'skimage.io', 'skimage.util',
        # To fix an error in a frozen build: unsupported operand type(s) for | operator.
        # See the same issue in the PyInstaller: https://github.com/pyinstaller/pyinstaller/issues/7249
        'PySide6.support.deprecated',
        'bsmu.vision.app',
        'bsmu.vision.core',
        'bsmu.vision.dnn',
        'bsmu.vision.plugins',
        'bsmu.vision.widgets',
    ]

    def __init__(
            self,
            file_dir: Path = Path(__file__).parent,
            script_path_relative_to_file_dir: Path = Path('src/bsmu/vision/app/__main__.py'),
            build_dir: Path | None = None,
            dist_dir: Path | None = None,

            app_name: str = bsmu.vision.app.__title__,
            app_version: str = '1.0.0',
            app_description: str = 'Base application for image visualization and processing '
                                   'that is easily extensible with plugins.',
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
        self._build_dir = self._file_dir / self._BUILD_DIR_NAME / self._build_name \
            if build_dir is None else build_dir
        self._dist_dir = self._file_dir / self._DIST_DIR_NAME if dist_dir is None else dist_dir

        self._app_name = app_name
        self._app_version = app_version
        self._app_description = f'{self._app_name} - {app_description}'
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
        script = self._file_dir / self._script_path_relative_to_file_dir
        target_name = self._build_name
        shortcut_name = self._app_name
        shortcut_dir = 'DesktopFolder'
        icon = self._icon_path

        gui_exe = Executable(
            script,
            base='Win32GUI',
            target_name=target_name,
            shortcut_name=shortcut_name,
            shortcut_dir=shortcut_dir,
            icon=icon,
        )
        cmd_exe = Executable(
            script,
            base=None,
            target_name=target_name + '-c',
            shortcut_name=shortcut_name,
            shortcut_dir=shortcut_dir,
            icon=icon,
        )

        setup(
            name=self._app_name,
            version=self._app_version,
            description=self._app_description,
            options={
                'build_exe': self._build_exe_options,
                'install_exe': self._install_exe_options,
                'bdist_msi': self._bdist_msi_options,
            },
            executables=[gui_exe, cmd_exe],
        )

    def _generate_default_build_exe_options(
            self,
            packages: List[str],
            packages_with_data: List[ModuleType],
    ) -> dict:
        list_of_data_file_tuples = generate_list_of_data_file_tuples_in_subprocess(packages_with_data)
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
            # 'include_msvcr': True,
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
