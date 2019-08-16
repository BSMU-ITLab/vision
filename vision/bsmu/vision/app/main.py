import sys

from bsmu.vision.app import App


def run_app():
    print('Run, Vision! Run!')

    app = App(sys.argv)
    app.run()


if __name__ == '__main__':
    run_app()
