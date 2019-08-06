import sys
from PySide2.QtWidgets import QApplication, QLabel
from PySide2.QtCore import QSettings
from PySide2.QtCore import QFileInfo


# settings = QSettings("MyTest", "TestApp")
settings = QSettings('configs/config.ini', QSettings.IniFormat)


class Label(QLabel):
    def resizeEvent(self, event):
        print("resize")
        super().resizeEvent(event)
        print(event.size().height())
        settings.setValue('MyTest/height', event.size().height())
        # settings.sync()


def run_main():
    print('Hello, Vision!')
    print(QFileInfo('configs/config.ini').absoluteFilePath())

    app = QApplication(sys.argv)


    # PluginManager::Enable Plugins:
    #
    # plugin_manager = PluginManager()



    label = Label("Hello World")

    h = settings.value('MyTest/height', 200)
    print('h', h)

    label.setGeometry(20, 20, 500, int(h))
    label.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    run_main()
