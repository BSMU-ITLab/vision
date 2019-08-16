from __future__ import annotations

from PySide2.QtCore import QObject, Signal


class Plugin(QObject):
    # setup_info = None

    enabled = Signal('Plugin')
    disabled = Signal('Plugin')

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

    @classmethod
    def name(cls):
        return cls.__name__
