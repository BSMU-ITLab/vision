import sys

from bsmu.vision.app import App


def run_app():
    print('Hello, Vision!')

    app = App(sys.argv)
    app.run()


if __name__ == '__main__':
    run_app()
