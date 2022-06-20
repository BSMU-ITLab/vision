"""
To build *.exe use the next command in the terminal:
    (vision) D:/Projects/vision>   python biocell/build.py build

To create an msi-installer:
    (vision) D:/Projects/vision>   python biocell/build.py bdist_msi
"""


from pathlib import Path

import bsmu.biocell.app
import bsmu.biocell.plugins
from bsmu.vision.app.builder import AppBuilder

if __name__ == '__main__':
    app_builder = AppBuilder(
        file_dir=Path(__file__).parent,
        script_path_relative_to_file_dir=Path('src/bsmu/biocell/app/__main__.py'),

        app_name='Biocell',
        app_version=bsmu.biocell.app.__version__,
        app_description='Application to detect prostate cancer on images of prostate tissue biopsies.',
        app_base=None,

        add_packages=['bsmu.biocell.app', 'bsmu.biocell.plugins'],
        add_packages_with_data=[bsmu.biocell.app, bsmu.biocell.plugins],
    )
    app_builder.build()
