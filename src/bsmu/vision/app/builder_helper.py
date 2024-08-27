from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import sys
from types import ModuleType
from typing import List

from bsmu.vision.core.data_file import DataFileProvider


# see: https://packaging.python.org/guides/creating-and-discovering-plugins/#using-namespace-packages
def iter_namespace_package_modules(namespace_package: ModuleType):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(namespace_package.__path__, namespace_package.__name__ + ".")


def find_modules_of_package_recursively(package: ModuleType, indent: int = 0):
    indent_str = indent * '\t'
    print(f'{indent_str}package:', package)
    for finder, name, ispkg in iter_namespace_package_modules(package):
        # print('Try to import:', name)  # Use this print to find current package or module with errors during import

        # Skip modules for which some dependencies are not installed
        try:
            module_or_package = importlib.import_module(name)
        except ModuleNotFoundError:
            print(f'Cannot import `{name}`, because during import some module not found')
            continue

        if ispkg:
            yield from find_modules_of_package_recursively(module_or_package, indent + 1)
        else:
            indent_str = (indent + 1) * '\t'
            print(f'{indent_str}module:', module_or_package)
            yield module_or_package


def find_modules_of_packages_recursively(packages: List[ModuleType], indent: int = 0):
    for package in packages:
        yield from find_modules_of_package_recursively(package, indent)


def generate_list_of_data_file_tuples(packages_with_data: List[ModuleType]) -> list[tuple[str, str]]:
    """
    :param packages_with_data: packages to search DataFileProvider classes
    :return: e.g. list of such tuples:
    ('full-path/vision-app/bsmu/vision/app/App.conf.yaml', 'data/bsmu.vision.app/configs/App.conf.yaml')
    full signature is:
    [('full path to the data file or dir', 'relative path to the data file or dir in the build folder'), ...]
    """
    # Use dictionary to remove duplicate values
    destination_data_path_by_absolute = {}
    for module in find_modules_of_packages_recursively(packages_with_data):
        class_name_value_pairs = inspect.getmembers(module, inspect.isclass)
        for cls_name, cls in class_name_value_pairs:
            # Skip classes, which were imported
            if cls.__module__ != module.__name__:
                continue

            if not issubclass(cls, DataFileProvider):
                continue

            for absolute_data_dir, frozen_rel_data_dir in cls.frozen_rel_data_dir_by_absolute().items():
                destination_data_path_by_absolute[absolute_data_dir] = frozen_rel_data_dir

    # Convert |destination_data_path_by_absolute| dict to list of tuples
    data_file_absolute_path_and_destination_tuples = \
        [(str(absolute_data_path), str(frozen_rel_data_path))
         for absolute_data_path, frozen_rel_data_path in destination_data_path_by_absolute.items()]

    return data_file_absolute_path_and_destination_tuples


def main():
    kwargs_str = sys.argv[1]
    kwargs = ast.literal_eval(kwargs_str)
    package_names = kwargs['package_names']
    packages = [importlib.import_module(package_name) for package_name in package_names]
    list_of_data_file_tuples = generate_list_of_data_file_tuples(packages)
    result = {'list_of_data_file_tuples': list_of_data_file_tuples}
    # Use the print statement to return the result via stdout
    print(result)


if __name__ == '__main__':
    main()
