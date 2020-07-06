from pathlib import Path

import bsmu.vision.app.main as parent_app


def run_app(child_config_paths: tuple = ()):
    print('Run, Bone Age! Run!')

    config_path = (Path(__file__).parent / 'configs').resolve()
    parent_app.run_app(child_config_paths + (config_path,))


if __name__ == '__main__':
    run_app()
