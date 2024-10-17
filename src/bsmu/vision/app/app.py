from __future__ import annotations

import argparse
import locale
import logging
import os
import sys
import traceback
import warnings
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QCoreApplication
from PySide6.QtWidgets import QApplication

from bsmu.vision.app.logger import ColoredFormatter, RotatingFileHandlerWithSeparator, SimpleFormatter
from bsmu.vision.app.plugin_manager import PluginManager
from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.config import UnitedConfig
from bsmu.vision.core.data_file import DataFileProvider
from bsmu.vision.core.freeze import is_app_frozen
from bsmu.vision.core.plugins import Plugin
from bsmu.vision.dnn.config import OnnxConfig


class App(QObject, DataFileProvider):
    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self, name: str, version: str):
        name_version = f'{name} {version}'

        arg_parser = argparse.ArgumentParser(prog=name_version)
        arg_parser.add_argument('-l', '--log-level', default=logging.getLevelName(logging.INFO))
        self._args = arg_parser.parse_args()

        self._init_logging()

        # Call the base method after the logging initialization
        super().__init__()

        logging.info(name_version)
        if not is_app_frozen():
            logging.info(f'Prefix: {sys.prefix}')
        logging.info(f'Executable: {sys.executable}')

        # Set to users preferred locale to output correct decimal point (comma or point):
        locale.setlocale(locale.LC_NUMERIC, '')

        # Pass base apps into config, because UnitedConfig of plugins need this info too
        UnitedConfig.configure_app_hierarchy(type(self), App)
        self._config = UnitedConfig(type(self), App)

        self._gui_enabled = self._config.value('enable-gui')
        self._qApp = QApplication(sys.argv) if self._gui_enabled else QCoreApplication(sys.argv)
        self._qApp.setApplicationName(name)
        self._qApp.setApplicationVersion(version)

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
            log_path = Path('logs')
            try:
                log_path.mkdir(exist_ok=True)
            except:
                # Create log files without common directory
                # if the application has no rights to create the directory
                log_path = Path('.')
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
