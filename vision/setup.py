import setuptools


with open('README.md', 'r') as fh:
    long_description = fh.read()


setuptools.setup(
    name='bsmu.vision',
    version='0.1.0',
    author='Ivan Kosik',
    author_email='ivankosik91@gmail.com',
    description='Base application for extension by plugins',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/IvanKosik/vision',
    packages=setuptools.find_namespace_packages(include=('bsmu.*',)),


    # package_data={
    #     # If any package contains *.yml files, include them:
    #     '': ['*.yml'],
    #     # And include any *.msg files found in the 'hello' package, too:
    #     # 'hello': ['*.msg'],
    # },

    data_files=[
        # ('config', ['bsmu/vision/App.cfg.yaml', 'bsmu/vision/dumped_config.yml'])
        ('config/bsmu/vision', ['bsmu/vision/App.cfg.yaml', 'bsmu/vision/dumped_config.yml'])
    ],


    install_requires=[
        'numpy',
        'PySide2',
        'ruamel.yaml',

        'bsmu.vision_core',
        'bsmu.vision.widgets'
    ],
    entry_points={
        ## 'gui_scripts': [
        'console_scripts': [
            'bsmu-vision = bsmu.vision.main:run_app',
        ]
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Development Status :: 1 - Planning',
        'Topic :: Software Development :: Version Control :: Git'
    ],
)
