import setuptools

from bsmu.vision.plugins.windows.main import MainWindowPlugin


setup_info = MainWindowPlugin.setup_info


setuptools.setup(
    name=setup_info.name,
    version=str(setup_info.version),
    py_modules=setup_info.py_modules,
    install_requires=setup_info.install_requires,
    author=setup_info.author,
    author_email=setup_info.author_email,
    description=setup_info.description,
    long_description=setup_info.long_description,
    long_description_content_type=setup_info.long_description_content_type,
    url=setup_info.url,
    classifiers=setup_info.classifiers
)
