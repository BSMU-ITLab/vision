import setuptools


setuptools.setup(
    name='bsmu.vision.widgets',
    version='0.0.1',
    author='Ivan Kosik',
    author_email='ivankosik91@gmail.com',

    packages=setuptools.find_namespace_packages(include=('bsmu.*',)),

    include_package_data=True,
    package_data={
        "": ["images/icons/*.svg"],
    },
)
