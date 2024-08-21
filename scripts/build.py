"""
1. Building the Executable (.exe):
   To build the executable, use the 'build' parameter:
       python build.py build

2. Creating an MSI Installer:
   To create an MSI installer, use the 'bdist_msi' parameter:
       python build.py bdist_msi

To build app, install all required packages using pip
For local dev packages use:
    pip install -e /path/to/package
Make sure that `/path/to/package` is the directory where pyproject.toml file is located.
"""


from pathlib import Path

from bsmu.vision.app.builder import AppBuilder

if __name__ == '__main__':
    app_builder = AppBuilder(
        project_dir=Path(__file__).resolve().parents[1],
    )
    app_builder.build()
