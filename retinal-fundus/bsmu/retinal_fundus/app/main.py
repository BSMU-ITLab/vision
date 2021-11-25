from bsmu.vision.app.base import App


class RetinalFundusApp(App):
    pass


def run_app():
    print('Run, Retinal Fundus! Run!')

    app = RetinalFundusApp()
    app.run()


if __name__ == '__main__':
    run_app()
