from bsmu.retinal_fundus.app import __title__, __version__
from bsmu.vision.app.base import App


class RetinalFundusApp(App):
    pass


def run_app():
    app = RetinalFundusApp(__title__, __version__)
    app.run()


if __name__ == '__main__':
    run_app()
