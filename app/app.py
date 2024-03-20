import time
import traceback

from flask import Flask, jsonify, render_template

from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot
from pyd2bot.thriftServer.pyd2botService.ttypes import (Certificate, JobFilter,
                                                        Path, PathType,
                                                        Session, SessionStatus,
                                                        SessionType,
                                                        TransitionType,
                                                        UnloadType, Vertex)
from pydofus2.com.ankamagames.dofus.kernel.net.DisconnectionReasonEnum import \
    DisconnectionReasonEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


def format_runtime(startTime):
    seconds = time.time() - startTime
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours == 0:
        if minutes == 0:
            result = f"{int(seconds)}s"
        else:
            result = f"{int(minutes)}m {int(seconds)}s"
    else:
        result = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    return result


def tail(filename, n=300):
    with open(filename, "r", encoding="ISO-8859-1") as file:
        lines = file.readlines()
        return "".join(lines[-n:])


class BotManagerApp:
    def __init__(self):
        self.app = Flask(__name__)
        self._running_bots = dict()
        self.setup_routes()

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template(
                "index.html", accounts=AccountManager.get_accounts(), runningBots=self._running_bots.values()
            )

        @self.app.route("/run/<account_id>/<character_id>/<action>")
        def run_action(account_id, character_id, action):
            try:
                accountkey = AccountManager.get_accountkey(account_id)
                character = AccountManager.get_character(accountkey, character_id)
                apikey = AccountManager.get_apikey(accountkey)
                cert = AccountManager.get_cert(accountkey)
                
                session = Session(
                    id=account_id,
                    character=character,
                    unloadType=UnloadType.BANK,
                    apikey=apikey,
                    cert=cert,
                )
                
                if action == "treasurehunt":
                    session.type = SessionType.TREASURE_HUNT

                elif action == "fight":
                    ankarnam_lvl1 = 154010883
                    ankarnal_lvl5 = 154010884
                    village_astrub = 191106048
                    ankama_coin_bouftou = 88082704
                    cania_pleines_rocheuses = 156240386
                    session.type = SessionType.FIGHT
                    session.path = Path(
                        id="astrub",
                        type=PathType.RandomSubAreaFarmPath,
                        startVertex=Vertex(mapId=village_astrub, zoneId=1),
                        transitionTypeWhitelist=[TransitionType.SCROLL, TransitionType.SCROLL_ACTION],
                    )
                    session.monsterLvlCoefDiff = 1.4

                elif action == "farm":
                    session.type = SessionType.FARM
                    session.path = Path(
                        id="amakna",
                        type=PathType.RandomAreaFarmPath,
                        startVertex=Vertex(mapId=191106048.0, zoneId=1),
                        subAreaBlacklist=[6, 482, 276, 277],  # exclude astrub cimetery, Milicluster, Bwork village
                    )
                    session.jobFilters = [
                        JobFilter(36, []),  # Pêcheur goujon
                        JobFilter(2, []),  # Bucheron,
                        JobFilter(26, []),  # Alchimiste
                        JobFilter(28, []),  # Paysan
                        JobFilter(1, [311]),  # Base : eau
                        JobFilter(24, []),  # Miner
                    ]
                    
                else:
                    return jsonify({"status": "error", "message": f"Unknown action {action}"})
                
                bot = Pyd2Bot(session)
                bot.addShutDownListener(self.on_bot_shutdown)
                self._running_bots[character.login] = {
                    "obj": bot,
                    "startTime": time.time(),
                    "character": character.name,
                    "activity": action,
                }
                bot.start()
                
            except Exception as e:
                return jsonify({"status": "error", "message": f"Error while running {action} : {e}"})
            
            return jsonify(
                {
                    "status": "success",
                    "message": f"Running {action} for account {account_id}, character {character_id}",
                }
            )

        @self.app.route("/stop/<botname>")
        def stop_action(botname):
            bot_data = self._running_bots.get(botname)
            if bot_data:
                bot = bot_data["obj"]
                bot.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "User wanted to stop bot")
            return jsonify({"status": "success", "message": f"Stopped bot {botname}"})

        @self.app.route("/get_running_bots")
        def get_running_bots():
            return jsonify(
                [
                    {
                        "name": bot["obj"].name,
                        "character": bot["character"],
                        "runTime": format_runtime(bot["startTime"]),
                        "status": SessionStatus._VALUES_TO_NAMES[bot["obj"].getState()],
                        "activity": bot["activity"],
                    }
                    for bot in self._running_bots.values()
                ]
            )

        @self.app.route("/get_log/<name>")
        def get_log(name):
            botlogger = Logger.getInstance(name)
            if not botlogger:
                return f"Bot {name} logger instance not found", 404
            filep = Logger.getInstance(name).outputFile
            log_data = tail(filep, 1000)
            return log_data, 200, {"Content-Type": "text/plain"}
        
        @self.app.route('/import_accounts', methods=['GET'])
        def import_accounts():
            try:
                import pythoncom

                pythoncom.CoInitialize()
                AccountManager.clear()
                AccountManager.import_launcher_accounts()
            except Exception as e:
                traceback.print_exc()
                print(f"Error while importing accounts: {e}")
                return jsonify({"message": f"Error while importing accounts: {e}"})
            return jsonify({"message": "Accounts imported successfully"})
        
    def on_bot_shutdown(self, login, message, reason):
        print(f"Bot {login} shutdown: {reason}\n{message}")
        # self._running_bots.pop(login)

    def run(self, debug=True):
        self.app.run(debug=debug)


if __name__ == "__main__":
    bot_manager_app = BotManagerApp()
    bot_manager_app.run(debug=True)
