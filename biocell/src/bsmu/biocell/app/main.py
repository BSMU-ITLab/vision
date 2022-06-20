from bsmu.vision.app.base import App


class BiocellApp(App):
    pass


def run_app():
    print('Run, Biocell! Run!')

    app = BiocellApp()
    app.run()


if __name__ == '__main__':
    run_app()
