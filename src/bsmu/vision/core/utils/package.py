import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PackageInfo:
    name: str
    path: Path


class PackageUtils:
    MODULE_SEPARATOR = '.'

    @classmethod
    def first_regular_package_info(cls, cls_type: type) -> PackageInfo:
        full_module_name = cls_type.__module__
        if full_module_name == '__main__':
            raise RuntimeError(
                f'Class {cls_type} is located in the "__main__" module. Cannot find its first regular package.')

        for index_char, char in enumerate(full_module_name):
            if char != cls.MODULE_SEPARATOR:
                continue

            # Extract the package name up to the current separator
            package_name = full_module_name[:index_char]
            package_module = sys.modules[package_name]
            # `sys.modules` will only work for modules that have already been imported.
            # For other cases `importlib.util.find_spec` should be used.

            if package_module.__file__ is not None:
                # The presence of `__file__` indicates that this is a regular (non-namespace) package.
                package_path = Path(package_module.__file__).parent.resolve()
                return PackageInfo(name=package_name, path=package_path)

    @classmethod
    def full_package_name(cls, cls_type: type) -> str:
        # Exclude the module name
        package_name, _, _ = cls_type.__module__.rpartition(cls.MODULE_SEPARATOR)
        return package_name
