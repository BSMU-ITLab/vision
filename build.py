"""
1. Building the Executable (.exe):
   To build the executable, use the 'build' parameter:
       python build.py build

2. Creating an MSI Installer:
   To create an MSI installer, use the 'bdist_msi' parameter:
       python build.py bdist_msi

To build app, install all required packages using pip
For local dev packages use:
    pip install -e /path/to/dir/with/setup.py
Or add them to the system path, e.g. using:
    sys.path.append('D:\\Projects\\vision\\vision-plugins')
"""


from pathlib import Path

import bsmu.vision.app as app
from bsmu.vision.app.builder import AppBuilder

if __name__ == '__main__':
    app_builder = AppBuilder(
        file_dir=Path(__file__).parent,

        app_version=app.__version__,
    )
    app_builder.build()
