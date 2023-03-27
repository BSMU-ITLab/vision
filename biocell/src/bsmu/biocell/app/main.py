from bsmu.biocell.app import __title__, __version__
from bsmu.vision.app.base import App


class BiocellApp(App):
    pass


def run_app():
    app = BiocellApp(__title__, __version__)
    app.run()


if __name__ == '__main__':
    run_app()
