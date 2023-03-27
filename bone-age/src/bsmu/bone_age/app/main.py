from bsmu.bone_age.app import __title__, __version__
from bsmu.vision.app.base import App


class BoneAgeApp(App):
    pass


def run_app():
    app = BoneAgeApp(__title__, __version__)
    app.run()


if __name__ == '__main__':
    run_app()
