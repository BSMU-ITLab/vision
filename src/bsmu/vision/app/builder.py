from __future__ import annotations

import ast
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from cx_Freeze import setup, Executable

import bsmu.vision.app
import bsmu.vision.plugins
from bsmu.vision.app import App
from bsmu.vision.core.config.united import UnitedConfig
from bsmu.vision.core.data_file import DataFileProvider
from bsmu.vision.core.utils.package import PackageUtils

if TYPE_CHECKING:
    from typing import Sequence


@dataclass
class ExtraFile:
    rel_project_path: Path
    url: str


def generate_list_of_data_file_tuples_in_subprocess(packages_with_data: list[ModuleType]) -> list[tuple[str, str]]:
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
    _CACHE_DIR_NAME = 'cache'
    _DIST_DIR_NAME = 'dist'

    _BASE_BUILD_EXE_PACKAGES = [
        'imageio',
        'numpy.core',
        'ruamel.yaml',
        'scipy.fftpack', 'scipy.ndimage',
        'skimage.color', 'skimage.io', 'skimage.util', 'skimage.exposure', 'skimage.draw', 'skimage.measure',
        # To fix an error in a frozen build: unsupported operand type(s) for | operator.
        # See the same issue in the PyInstaller: https://github.com/pyinstaller/pyinstaller/issues/7249
        'PySide6.support.deprecated',
        'bsmu.vision',
    ]

    def __init__(
            self,
            project_dir: Path,
            app_class: type[App] = App,
            extra_files: Sequence[ExtraFile] | None = (
                ExtraFile(
                    Path('scripts/run-debug.bat'),
                    'https://raw.githubusercontent.com/BSMU-ITLab/vision/refs/heads/main/scripts/run-debug.bat',
                ),
            ),

            script_path_relative_to_project_dir: Path = Path('src/bsmu/vision/app/__main__.py'),
            icon_path_relative_to_project_dir: Path | None = None,

            build_dir: Path | None = None,
            dist_dir: Path | None = None,

            add_packages: list[str] | None = None,
            packages_with_data: list[ModuleType] | None = None,
            add_packages_with_data: list[ModuleType] | None = None,

            build_exe_options: dict | None = None,
            install_exe_options: dict | None = None,
            bdist_msi_options: dict | None = None,
    ):
        self._project_dir = project_dir
        self._app_class = app_class
        self._extra_files = extra_files

        self._script_path_relative_to_project_dir = script_path_relative_to_project_dir
        if icon_path_relative_to_project_dir is None:
            self._icon_path = Path(__file__).parent / 'images/icons/vision.ico'
        else:
            self._icon_path = self._project_dir / icon_path_relative_to_project_dir

        self._build_name = f'{self._app_class.TITLE.replace(" ", "")}-{self._app_class.VERSION}'
        self._build_dir = self._project_dir / self._BUILD_DIR_NAME / self._build_name \
            if build_dir is None else build_dir
        self._dist_dir = self._project_dir / self._DIST_DIR_NAME if dist_dir is None else dist_dir

        self._app_description = f'{self._app_class.TITLE} - {self._app_class.DESCRIPTION}'

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
        script = self._project_dir / self._script_path_relative_to_project_dir
        target_name = self._build_name
        shortcut_name = self._app_class.TITLE
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
            name=self._app_class.TITLE,
            version=self._app_class.VERSION,
            description=self._app_description,
            options={
                'build_exe': self._build_exe_options,
                'install_exe': self._install_exe_options,
                'bdist_msi': self._bdist_msi_options,
            },
            executables=[gui_exe, cmd_exe],
        )

    def _cache_build_dir(self) -> Path:
        return self._project_dir / self._BUILD_DIR_NAME / self._CACHE_DIR_NAME

    def _generate_default_build_exe_options(
            self,
            packages: list[str],
            packages_with_data: list[ModuleType],
    ) -> dict:
        src_to_dst_config_dir_tuples = self._generate_src_to_dst_config_dir_tuples()
        list_of_data_file_tuples = generate_list_of_data_file_tuples_in_subprocess(packages_with_data)
        include_files: list[tuple[str, str] | str] = src_to_dst_config_dir_tuples + list_of_data_file_tuples
        if self._extra_files:
            include_files += self._get_or_download_extra_files()
        print('include_files: ', include_files)

        config_modules_to_exclude = self._generate_config_modules_to_exclude()
        frozen_rel_data_paths = [data_file_tuple[1] for data_file_tuple in list_of_data_file_tuples]
        data_modules_to_exclude = self._generate_data_modules_to_exclude(frozen_rel_data_paths)
        excludes = ['tkinter', 'scipy.spatial.cKDTree'] + config_modules_to_exclude + data_modules_to_exclude
        print('excludes: ', excludes)

        return {
            'build_exe': self._build_dir,
            'packages': packages,
            'excludes': excludes,
            'includes': ['numpy', 'scipy.sparse.csgraph._validation'],
            'include_files': include_files,
            # 'include_msvcr': True,
        }

    def _generate_src_to_dst_config_dir_tuples(self) -> list[tuple[str, str]]:
        """
        Generate a list of tuples containing source and destination (frozen) configuration directories.
        """
        src_to_dst_config_dir_tuples = []
        dst_config_dir = self._app_class.frozen_rel_config_dir()
        for base_app_class in self._app_class.base_app_classes():
            src_to_dst_config_dir_tuples.append((str(base_app_class.unfrozen_config_dir()), str(dst_config_dir)))
            # Each base app's configuration should be placed in a subdirectory named UnitedConfig.BASE_DIR_NAME
            dst_config_dir /= UnitedConfig.BASE_DIR_NAME
        return src_to_dst_config_dir_tuples

    def _get_or_download_extra_files(self) -> list[str]:
        extra_file_paths: list[str] = []
        for extra_file in self._extra_files:
            try:
                extra_file_paths.append(self._get_or_download_extra_file(extra_file))
            except (urllib.error.URLError, urllib.error.HTTPError) as e:
                print(f'Warning: Could not download {extra_file.rel_project_path.name} from {extra_file.url}: {e}')
        return extra_file_paths

    def _get_or_download_extra_file(self, extra_file: ExtraFile) -> str:
        # Check if the file exists in the project directory
        absolute_file_path = self._project_dir / extra_file.rel_project_path
        if absolute_file_path.exists():
            return str(absolute_file_path)

        # Check if the file is cached
        cached_file_path = self._cache_build_dir() / extra_file.rel_project_path
        if not cached_file_path.exists():
            # Download and cache the file
            cached_file_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(extra_file.url, cached_file_path)

        return str(cached_file_path)

    def _generate_config_modules_to_exclude(self) -> list[str]:
        excluded_config_modules = []
        for base_app_class in self._app_class.base_app_classes():
            base_app_config_module = PackageUtils.MODULE_SEPARATOR.join(
                (base_app_class.first_regular_package_info().name, UnitedConfig.DIR_NAME))
            excluded_config_modules.append(base_app_config_module)
        return excluded_config_modules

    @staticmethod
    def _generate_data_modules_to_exclude(frozen_rel_data_paths: list[str]) -> list[str]:
        data_modules_to_exclude = []
        for frozen_rel_data_path in frozen_rel_data_paths:
            data_module_to_exclude = Path(frozen_rel_data_path).relative_to(DataFileProvider.frozen_rel_resources_dir())
            data_module_to_exclude = str(data_module_to_exclude).replace('\\', '.')
            data_modules_to_exclude.append(data_module_to_exclude)
        return data_modules_to_exclude

    def _generate_default_install_exe_options(self) -> dict:
        return {
            'build_dir': self._build_dir,
        }

    def _generate_default_bdist_msi_options(self) -> dict:
        return {
            'bdist_dir': self._dist_dir / 'temp',
            'dist_dir': str(self._dist_dir),
        }
