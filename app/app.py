import logging
import time
import sys
import traceback
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
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
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import HtmlFormatter, Logger
import signal

def signal_handler(sig, frame):
    print('You pressed Ctrl+C or the server is reloading!')
    # Insert your cleanup code here
    for bot_data in BotManagerApp._running_bots.values():
        bot = bot_data["obj"]
        bot.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "Brutal shutdown because of app reload")
        bot.join()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class SocketIOHandler(logging.Handler):
    def __init__(self, socketio: 'SocketIO', batch_time=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.socketio = socketio
        self.batch_time = batch_time
        self.batch = []
        self.timer = None

    def emit(self, record):
        log_entry = self.format(record)
        self.batch.append(log_entry)
        if not self.timer:
            self.timer = BenchmarkTimer(self.batch_time, self.flush)
            self.timer.start()

    def flush(self):
        self.socketio.emit('log_message_batch', self.batch)
        self.batch.clear()
        self.timer = None
        
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

class BotManagerApp:
    _running_bots = dict()
    
    def __init__(self):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self._log_handler = None
        self.setup_routes()

    @staticmethod
    def get_basic_session(account_id, character_id) -> Session:
        accountkey = AccountManager.get_accountkey(account_id)
        character = AccountManager.get_character(accountkey, character_id)
        apikey = AccountManager.get_apikey(accountkey)
        cert = AccountManager.get_cert(accountkey)
        return Session(
            id=account_id,
            character=character,
            unloadType=UnloadType.BANK,
            apikey=apikey,
            cert=cert,
        )

    def start_bot_session(self, session: Session, action: str):
        bot = Pyd2Bot(session)
        bot.addShutDownListener(self.on_bot_shutdown)
        self._running_bots[session.character.login] = {
            "obj": bot,
            "startTime": time.time(),
            "character": session.character.name,
            "activity": action,
        }
        bot.start()

    def teardown(self, *args):
        for bot_data in self._running_bots.values():
            bot = bot_data["obj"]
            bot.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "Brutal shutdown because of app reload")
        self.socketio.stop()
    
    def setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template(
                "index.html", accounts=AccountManager.get_accounts(), runningBots=self._running_bots.values()
            )

        @self.app.route('/fight-paths', methods=['GET'])
        def get_fight_paths():
            paths = {
                "Ankarnam (lvl1)": 154010883,
                "Ankarnam (lvl5)": 154010884,
                "Astrub village": 191106048
            }
            # You might want to fetch these values from a database or another service in a real application
            return jsonify({"paths": paths})

        @self.app.route('/solo-fight', methods=['POST'])
        def solo_fight():
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400

            data = request.get_json()

            # Extracting the necessary information from the request
            account_id = data.get('account_id')
            character_id = data.get('character_id')
            path_value = data.get('path_value')
            try:
                monster_lvl_coef_diff = float(data.get('monsterLvlCoefDiff'))  # Explicitly convert to float
            except ValueError:
                return jsonify({"error": "Invalid format for monsterLvlCoefDiff. A float is required."}), 400


            # Placeholder for your logic to process the solo fight
            session = self.get_basic_session(account_id, character_id)
            session.type = SessionType.FIGHT
            session.path = Path(
                id="astrub",
                type=PathType.RandomSubAreaFarmPath,
                startVertex=Vertex(mapId=path_value, zoneId=1),
                transitionTypeWhitelist=[TransitionType.SCROLL, TransitionType.SCROLL_ACTION],
            )
            session.monsterLvlCoefDiff = monster_lvl_coef_diff
            # For example, validate the input and then update the database or process the game logic
            print(f"Processing solo fight for account {account_id}, character {character_id}, on path {path_value} with monster level coefficient difficulty {monster_lvl_coef_diff}")

            self.start_bot_session(session, "solo-fight")

            # Responding with a success message or any other relevant information
            return jsonify({"message": "Solo fight initiated successfully"}), 200
            
        @self.app.route("/run/<account_id>/<character_id>/<action>")
        def run_action(account_id, character_id, action):
            try:
                session = self.get_basic_session(account_id, character_id)
                
                if action == "treasurehunt":
                    session.type = SessionType.TREASURE_HUNT

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
                
                self.start_bot_session(session, action)
                
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
            result = []
            for bot in self._running_bots.values():
                bot_data = {
                    "name": bot["obj"].name,
                    "character": bot["character"],
                    "runTime": format_runtime(bot["startTime"]),
                    "status": SessionStatus._VALUES_TO_NAMES[bot["obj"].getState()],
                    "activity": bot["activity"],
                }
                playermanager = PlayedCharacterManager.getInstance(bot["obj"].name)
                if playermanager and playermanager.infos:
                    bot_data["level"] = playermanager.infos.level
                result.append(bot_data)
            return jsonify(result)

        @self.app.route("/watch-log", methods=['POST'])
        def watch_log():
            data = request.json
            action = data['action']
            
            if action == "start":
                bot_name = data['name']
                if self._log_handler:
                    return {"error": "Log watching already started"}, 400
    
    
                botlogger = Logger.getInstance(bot_name)
                if not botlogger:
                    return {"error": f"Bot {bot_name} logger instance not found"}, 400
                handler = SocketIOHandler(self.socketio)
                formatter = HtmlFormatter(
                    "%(asctime)s.%(msecs)03d | %(levelname)s | [%(module)s] %(message)s", datefmt="%H:%M:%S"
                )
                handler.setFormatter(formatter)
                botlogger.addHandler(handler)
                self._log_handler = {"bot": bot_name, "obj": handler}
                
                return {"message": "Log watching started"}, 200
            
            elif action == "stop":
                if self._log_handler:
                    botlogger = Logger.getInstance(self._log_handler["bot"])
                    botlogger.removeHandler(self._log_handler["obj"])
                    self._log_handler = None
                    return {"message": "Log watching stopped"}, 200

            return {"error": "Invalid action or name"}, 400
        
        @self.app.route('/import_accounts', methods=['GET'])
        def import_accounts():
            try:
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

    def run(self, debug=True, port=5000):
        self.socketio.run(self.app, debug=debug, port=port)


if __name__ == "__main__":
    bot_manager_app = BotManagerApp()
    bot_manager_app.run(debug=False)
