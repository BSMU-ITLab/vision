from bsmu.vision.app import __title__, __version__
from bsmu.vision.app.base import App


def run_app():
    app = App(__title__, __version__)
    app.run()


if __name__ == '__main__':
    run_app()
