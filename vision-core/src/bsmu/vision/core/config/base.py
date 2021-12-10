from __future__ import annotations

from ruamel.yaml import YAML


class Config:
    def __init__(self, path: Path):
        self.path = path
        print(f'Config path: {self.path.absolute()}')

        self.data = None
        self.yaml = YAML()

    def load(self):
        if self.path.exists():
            with open(self.path, 'r') as file:
                self.data = self.yaml.load(file)
        return self.data

    def save(self):
        with open(self.path, 'w') as file:
            self.yaml.dump(self.data, file)
