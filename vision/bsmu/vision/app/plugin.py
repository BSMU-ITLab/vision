from __future__ import annotations

from PySide2.QtCore import QObject, Signal


class Plugin(QObject):
    # setup_info = None

    enabled = Signal(QObject)  # Have to be a Plugin instead of QObject, but the Plugin is not defined yet
    disabled = Signal(QObject)  # Same as above

    def __init__(self, app: App):
        super().__init__()

        self.app = app

        self.print_action('init')

    def __del__(self):
        self.print_action('del')

    def enable(self):
        self.print_action('enable')
        self._enable()
        self.enabled.emit(self)

    def _enable(self):
        pass

    def disable(self):
        self.print_action('disable')
        self._disable()
        self.disabled.emit(self)

    def _disable(self):
        pass

    def print_action(self, action_str):
        print(f'{action_str} {self.name()} plugin')

    def config(self, relative_config_file_path):
        import sys
        from pathlib import Path
        configs_parent_dir = Path(sys.modules[self.__module__].__file__).parent
        # import inspect
        # plugin_file_path = inspect.getfile(self.__class__)
        united_config = self.app.config_uniter.unite_configs(configs_parent_dir, relative_config_file_path)
        return united_config

    @classmethod
    def name(cls):
        return cls.__name__
