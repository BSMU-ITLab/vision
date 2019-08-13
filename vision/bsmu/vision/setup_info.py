from __future__ import annotations


class SetupInfo:
    def __init__(self, name: str, version: Version,
                 py_modules: tuple = (),
                 install_requires: tuple = ('bsmu-vision',),
                 description: str = '', long_description: str = '',
                 long_description_content_type: str = 'text/markdown',
                 url: str = 'https://github.com/IvanKosik/vision',
                 author: str = 'Ivan Kosik', author_email: str = 'ivankosik91@gmail.com',
                 classifiers=('Programming Language :: Python :: 3',
                              'License :: OSI Approved :: BSD License',
                              'Operating System :: OS Independent',
                              'Development Status :: 1 - Planning',
                              'Topic :: Software Development :: Version Control :: Git')):
        self.name = name
        self.version = version
        self.py_modules = py_modules
        self.install_requires = install_requires
        self.description = description
        self.long_description = long_description
        self.long_description_content_type = long_description_content_type
        self.url = url
        self.author = author
        self.author_email = author_email
        self.classifiers = classifiers
