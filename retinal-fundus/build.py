"""
To build *.exe use the next command in the terminal:
    (vision) D:/Projects/vision/retinal-fundus>   python build.py build

To create an msi-installer:
    (vision) D:/Projects/vision/retinal-fundus>   python build.py bdist_msi
"""


from pathlib import Path

import bsmu.retinal_fundus.app
import bsmu.retinal_fundus.plugins
from bsmu.vision.app.builder import AppBuilder

if __name__ == '__main__':
    app_builder = AppBuilder(
        file_dir=Path(__file__).parent,
        script_path_relative_to_file_dir=Path('src/bsmu/retinal_fundus/app/__main__.py'),

        app_name=bsmu.retinal_fundus.app.__title__,
        app_version=bsmu.retinal_fundus.app.__version__,
        app_description='Application to analyze disk, cup, vessels parameters '
                        'and to detect multiple sclerosis features on retinal fundus images.',
        # app_base=None,

        add_packages=['bsmu.retinal_fundus.app', 'bsmu.retinal_fundus.plugins'],
        add_packages_with_data=[bsmu.retinal_fundus.app, bsmu.retinal_fundus.plugins],
    )
    app_builder.build()
