from PyQt5 import QtWidgets
from pyd2bot.Pyd2Bot import Pyd2Bot


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    
    def __init__(self, icon, bots: list[Pyd2Bot], parent=None, title="bots"):
        super(SystemTrayIcon, self).__init__(icon, parent)
        self.setToolTip(title)
        
        menu = QtWidgets.QMenu(parent)
        exit_action = menu.addAction("Stop Bot")
        exit_action.triggered.connect(self.stop_bot)
        self.bots = bots
        self.setContextMenu(menu)

    def stop_bot(self):
        print("Stopping the bots ...")
        for bot in self.bots:
            bot.shutdown("User wanted to stop the bot")
        for bot in self.bots:
            bot.join()
        QtWidgets.QApplication.quit()