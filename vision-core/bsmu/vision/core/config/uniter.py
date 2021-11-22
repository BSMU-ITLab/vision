from __future__ import annotations

import sys
from pathlib import Path

from ruamel.yaml import YAML


class ConfigUniterOld:
    def __init__(self, child_config_paths: tuple = ()):
        self.child_config_paths = child_config_paths

    def unite_configs(self, base_config_dir, config_file_name: str, config_file_full_name: str = ''):
        if getattr(sys, 'frozen', False):
            # The application is frozen into *.exe
            base_config_dir = Path(sys.executable).parent / 'configs'

        if not config_file_full_name:
            config_file_full_name = config_file_name

        yaml = YAML()

        with open(base_config_dir / config_file_name) as file:
            config_data = yaml.load(file)

        for child_config_dir in reversed(self.child_config_paths):
            child_config_file_path = child_config_dir / config_file_full_name
            if child_config_file_path.exists():
                with open(child_config_file_path) as fp:
                    child_config_data = yaml.load(fp)
                    if child_config_data is None:
                        child_config_data = {}

                for child_config_key, child_config_value in child_config_data.items():
                    assert child_config_key in config_data, 'child project has config key, which parent does not'
                    config_data[child_config_key] = child_config_value

        # create a new file with merged yaml
        # yaml.dump(data, file('united.yaml', 'w'))

        united_config = UnitedConfigOld(self.child_config_paths, config_data, yaml)
        return united_config


class UnitedConfigOld:
    def __init__(self, childs, data, yaml):
        self.childs = childs
        self.data = data
        self.yaml = yaml

    def save(self):
        raise NotImplementedError()
