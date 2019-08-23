import sys

from bsmu.vision.app import App

print('VVV: ', __file__)


def run_app(childs=()):
    # run_app.test_var = []

    print('Run, Vision! Run!')
    # print('VVV: ', __file__)
    # print('VVV test_var', run_app.test_var)
    # print('VVV child', childs + (__file__,))

    # print('VVV child', (*childs, __file__))

    print('from main', sys.modules[App.__module__].__file__)

    # app = App(sys.argv, childs + (__file__,))
    app = App(sys.argv, childs)
    app.run()


if __name__ == '__main__':
    run_app()
