from PyQt5 import QtWidgets


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    
    def __init__(self, icon, bot, parent=None):
        super(SystemTrayIcon, self).__init__(icon, parent)
        self.setToolTip(bot.name)
        
        menu = QtWidgets.QMenu(parent)
        exit_action = menu.addAction("Stop Bot")
        exit_action.triggered.connect(self.stop_bot)
        self.bot = bot
        self.setContextMenu(menu)

    def stop_bot(self):
        print("Stopping the bot...")
        # Add your bot stopping logic here
        self.bot.shutdown()
        self.bot.join()
        QtWidgets.QApplication.quit()