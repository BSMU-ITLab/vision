from bsmu.vision.app import App, __title__, __version__


def run_app():
    app = App(__title__, __version__)
    app.run()


if __name__ == '__main__':
    run_app()
