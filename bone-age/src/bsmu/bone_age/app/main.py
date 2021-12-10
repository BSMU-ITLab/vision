from bsmu.vision.app.base import App


class BoneAgeApp(App):
    pass


def run_app():
    print('Run, Bone Age! Run!')

    app = BoneAgeApp()
    app.run()


if __name__ == '__main__':
    run_app()
