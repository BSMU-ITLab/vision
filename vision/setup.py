import setuptools


with open('README.md', 'r') as fh:
    long_description = fh.read()


setuptools.setup(
    name='bsmu-vision',
    version='0.0.1',
    author='Ivan Kosik',
    author_email='ivankosik91@gmail.com',
    description='Base application for extension by plugins',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/IvanKosik/vision',
    packages=setuptools.find_namespace_packages(include=['bsmu.*']),
    entry_points={
        ## 'gui_scripts': [
        'console_scripts': [
            'bsmu-vision = bsmu.vision.main:run_main',
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
