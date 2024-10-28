from __future__ import annotations

import argparse
import locale
import logging
import os
import sys
import traceback
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QCoreApplication
from PySide6.QtWidgets import QApplication

from bsmu.vision import __title__, __version__, __description__
from bsmu.vision.app.logger import ColoredFormatter, RotatingFileHandlerWithSeparator, SimpleFormatter
from bsmu.vision.app.plugin_manager import PluginManager
from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.config import UnitedConfig
from bsmu.vision.core.data_file import DataFileProvider
from bsmu.vision.core.freeze import is_app_frozen
from bsmu.vision.core.plugins import Plugin
from bsmu.vision.core.utils.hierarchy import HierarchyUtils
from bsmu.vision.dnn.config import OnnxConfig

if TYPE_CHECKING:
    from typing import Sequence


class App(QObject, DataFileProvider):
    TITLE: str = __title__
    VERSION: str = __version__
    DESCRIPTION: str = __description__

    # Keeps the sequence of classes from the most derived to the base App class
    _BASE_APP_CLASSES: Sequence[type[App]] | None = None

    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    @classmethod
    def __init_subclass__(cls, title: str = '', version: str = '', description: str = '', **kwargs):
        super().__init_subclass__(**kwargs)

        # TODO: The `title`, `version`, and `description` parameters are unused because App inherits from QObject.
        #  And if a derived class passes additional arguments (e.g., class DerivedApp(App, title='Derived')),
        #  PySide 6.7.2 raises a TypeError: sbktype() takes at most 3 arguments (4 given).
        #  Once this issue is resolved, `title` and `version` will be mandatory (no default values),
        #  and all method arguments will be used.
        # cls.TITLE = title
        # cls.VERSION = version
        # cls.DESCRIPTION = description

        # Initialize `cls._BASE_APP_CLASSES` to None for each subclass
        # to ensure each one has its own attribute that can be set independently.
        cls._BASE_APP_CLASSES = None

    def __init__(self):
        title_version = f'{self.TITLE} {self.VERSION}'
        arg_parser = argparse.ArgumentParser(prog=title_version)
        arg_parser.add_argument('-l', '--log-level', default=logging.getLevelName(logging.INFO))
        self._args = arg_parser.parse_args()

        self._init_logging()

        # Call the base method after the logging initialization
        super().__init__()

        logging.info(title_version)
        if not is_app_frozen():
            logging.info(f'Prefix: {sys.prefix}')
        logging.info(f'Executable: {sys.executable}')

        # Set to users preferred locale to output correct decimal point (comma or point):
        locale.setlocale(locale.LC_NUMERIC, '')

        # Pass app class into the config, because we need access to `App.base_app_classes()`
        UnitedConfig.configure_app_class(type(self))
        self._config = UnitedConfig(type(self), App)

        self._gui_enabled = self._config.value('enable-gui')
        self._qApp = QApplication(sys.argv) if self._gui_enabled else QCoreApplication(sys.argv)
        self._qApp.setApplicationName(self.TITLE)
        self._qApp.setApplicationVersion(self.VERSION)

        ThreadPool.create_instance(
            self._config.value('max_general_thread_count'),
            self._config.value('max_dnn_thread_count'))

        if self._config.value('warn-with-traceback'):
            warnings.showwarning = warn_with_traceback
            warnings.simplefilter('always')

        OnnxConfig.providers = self._config.value('onnx_providers')

        os.environ['OPENCV_IO_MAX_IMAGE_PIXELS'] = str(self._config.value('opencv_io_max_image_pixels'))

        self._plugin_manager = PluginManager(self)
        self._plugin_manager.plugin_enabled.connect(self.plugin_enabled)
        self._plugin_manager.plugin_disabled.connect(self.plugin_disabled)

        configured_plugins = self._config.value('plugins')
        if configured_plugins is not None:
            self._plugin_manager.enable_plugins(configured_plugins)

    @classmethod
    def base_app_classes(cls) -> Sequence[type[App]]:
        if cls._BASE_APP_CLASSES is None:
            cls._BASE_APP_CLASSES = HierarchyUtils.inheritance_hierarchy(cls, App)
        return cls._BASE_APP_CLASSES

    @classmethod
    def config_dir(cls) -> Path:
        return cls.frozen_absolute_config_dir() if is_app_frozen() else cls.unfrozen_config_dir()

    @classmethod
    def unfrozen_config_dir(cls) -> Path:
        return cls.first_regular_package_info().path / UnitedConfig.DIR_NAME

    @classmethod
    def frozen_rel_config_dir(cls) -> Path:
        return cls.frozen_rel_data_dir() / UnitedConfig.DIR_NAME

    @classmethod
    def frozen_absolute_config_dir(cls) -> Path:
        return cls.frozen_exe_dir() / cls.frozen_rel_config_dir()

    @property
    def gui_enabled(self) -> bool:
        return self._gui_enabled

    def enabled_plugins(self) -> list[Plugin]:
        return self._plugin_manager.enabled_plugins

    def run(self):
        sys.exit(self._qApp.exec())

    def _init_logging(self):
        log_level_str = self._args.log_level
        log_level = getattr(logging, log_level_str.upper(), None)
        if not isinstance(log_level, int):
            raise ValueError(f'Invalid log level: {log_level_str}')

        handlers = []
        if is_app_frozen():
            log_path = self.frozen_absolute_data_dir() / 'logs'
            try:
                log_path.mkdir(exist_ok=True)
            except:
                # Create log files without common directory
                # if the application has no rights to create the directory
                log_path = self.frozen_exe_dir()
            file_handler = RotatingFileHandlerWithSeparator(
                filename=log_path / f'log-{log_level_str.lower()}.log',
                maxBytes=2_097_152,  # 2 MB
                backupCount=1,
                encoding='utf-8')
            file_handler.setFormatter(SimpleFormatter())
            handlers.append(file_handler)

            stream_handler_formatter = SimpleFormatter()
        else:
            stream_handler_formatter = ColoredFormatter()

        stream_handler = logging.StreamHandler(stream=sys.stdout)
        stream_handler.setFormatter(stream_handler_formatter)
        handlers.append(stream_handler)
        logging.basicConfig(level=log_level, handlers=handlers)


def warn_with_traceback(message, category, filename, lineno, file=None, line=None):
    log = file if hasattr(file, 'write') else sys.stderr
    traceback.print_stack(file=log)
    log.write(warnings.formatwarning(message, category, filename, lineno, line))
