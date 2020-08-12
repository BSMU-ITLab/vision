# To build *.exe use the next command in the terminal:
# (vision) D:\Projects\vision>   python vision/build.py build

# To create an msi-installer:
# (vision) D:\Projects\vision>   python vision/build.py bdist_msi


from pathlib import Path

from cx_Freeze import setup, Executable


FILE_DIR = Path(__file__).parent
BUILD_DIR = FILE_DIR / 'build'
DIST_DIR = FILE_DIR / 'dist'


# Dependencies are automatically detected, but it might need fine tuning
build_exe_options = {
    'packages': [
        'scipy.fftpack', 'scipy.ndimage',
        'skimage.io', 'skimage.util', 'skimage.color',
        'numpy.core',
        'bsmu/vision/app', 'bsmu/vision/plugins',
        'bsmu/vision/widgets',
        'bsmu/vision_core',
    ],
    'namespace_packages': ['ruamel.yaml'],
    'excludes': ['tkinter', 'scipy.spatial.cKDTree'],  # to fix the current bug
    'includes': ['numpy', 'scipy.sparse.csgraph._validation'],
    'build_exe': BUILD_DIR,
}

install_exe_options = {
    'build_dir': BUILD_DIR,
}

bdist_msi_options = {
    'bdist_dir': DIST_DIR / 'temp',
    'dist_dir': str(DIST_DIR),
}

# GUI applications require a different base on Windows (the default is for a console application).
app_base = None
# if sys.platform == 'win32':
#     app_base = 'Win32GUI'
#     print('Win32GUI')
# else:
#     print('app_base = None')

setup(
    name='Vision',
    version='0.0.1',
    description='Base application for extension by plugins',
    options={
        'build_exe': build_exe_options,
        'install_exe': install_exe_options,
        'bdist_msi': bdist_msi_options,
    },
    executables=[Executable(
        FILE_DIR / 'bsmu/vision/app/main.py',
        base=app_base,
        shortcutName='Bone Age',
        shortcutDir='DesktopFolder',
    )]
)
