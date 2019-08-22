from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML


class ConfigUniter:
    def __init__(self, childs):
        assert childs, 'At least one child!!!'

        self.childs = [Path(child).parent.resolve() for child in childs]
        self.root = self.childs[-1]

    def unite_configs(self, config_relative_path):
        yaml = YAML()

        with open(self.root / config_relative_path) as file:
            data = yaml.load(file)

        for child in reversed(self.childs[:-1]):
            with open(child / config_relative_path) as fp:
                child_data = yaml.load(fp)

            for child_key, child_value in child_data.items():
                assert child_key in data, 'child project has config key, which parent DOES NOT HAVE'
                data[child_key] = child_value

        # create a new file with merged yaml
        # yaml.dump(data, file('united.yaml', 'w'))

        united_config = UnitedConfig(self.childs, data, yaml)
        return united_config


class UnitedConfig:
    def __init__(self, childs, data, yaml):
        self.childs = childs
        self.data = data
        self.yaml = yaml

    def save(self):
        raise NotImplementedError()
