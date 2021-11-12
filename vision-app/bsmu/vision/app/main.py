import sys

from bsmu.vision.app import App


def run_app(child_config_paths: tuple = ()):
    print('Run, Vision! Run!')

    app = App(sys.argv, child_config_paths)
    app.run()


if __name__ == '__main__':
    run_app()
