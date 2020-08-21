from __future__ import annotations

from typing import Optional, Tuple

from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class BoneAgeMainWindow(MainWindow):
    def __init__(self, title: str = '', menu_order: Optional[Tuple[MainMenu]] = None):
        super().__init__(title, menu_order)


class BoneAgeMainWindowPlugin(MainWindowPlugin):
    # setup_info = SetupInfo(name='bsmu-vision-main-window',
    #                        version=Version(0, 0, 1),
    #                        py_modules=('main',))

    def __init__(self, app: App):
        super().__init__(app, BoneAgeMainWindow)
