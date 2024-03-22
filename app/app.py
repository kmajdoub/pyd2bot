import json
import logging
import os
import time
import sys
import traceback
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot
from pyd2bot.thriftServer.pyd2botService.ttypes import (
    JobFilter,
    Path,
    PathType,
    Session,
    SessionStatus,
    SessionType,
    TransitionType,
    UnloadType,
    Vertex,
)
from pydofus2.com.ankamagames.dofus.kernel.net.DisconnectionReasonEnum import DisconnectionReasonEnum
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import HtmlFormatter, Logger
import signal


def signal_handler(sig, frame):
    print("You pressed Ctrl+C or the server is reloading!")
    # Insert your cleanup code here
    for bot_data in BotManagerApp._running_bots.values():
        bot = bot_data["obj"]
        bot.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "Brutal shutdown because of app reload")
        bot.join()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

paths = {
    "Ankarnam (lvl1)": {
        "id": 'ankarnam_lvl1',
        "type": PathType.RandomSubAreaFarmPath,
        "startVertex": {"mapId": 154010883, "zoneId": 1},
        "transitionTypeWhitelist": [TransitionType.SCROLL, TransitionType.SCROLL_ACTION],
    },
    "Ankarnam (lvl5)": {
        "id": 'ankarnam_lvl5',
        "type": PathType.RandomSubAreaFarmPath,
        "startVertex": {"mapId": 154010884, "zoneId": 1},
        "transitionTypeWhitelist": [TransitionType.SCROLL, TransitionType.SCROLL_ACTION],
    },
    "Astrub village": {
        "id": 'astrub_village',
        "type": PathType.RandomSubAreaFarmPath,
        "startVertex": {"mapId": 191106048, "zoneId": 1},
        "transitionTypeWhitelist": [TransitionType.SCROLL, TransitionType.SCROLL_ACTION],
    },
}

def json_to_path(path_json) -> Path:
    pth = Path(
        id=path_json["id"],
        type=path_json["type"],
        transitionTypeWhitelist=path_json.get("transitionTypeWhitelist"),
        mapIds=path_json.get("mapIds"),
    )
    if "startVertex" in path_json:
        pth.startVertex = Vertex(mapId=path_json["startVertex"]["mapId"], zoneId=path_json["startVertex"]["zoneId"])
    return pth

staticdir = os.path.join(os.path.dirname(__file__), "static")
dofus_data_file = os.path.join(staticdir, "dofusData", "dofus_data.json")
with open(dofus_data_file, "r") as f:
    dofus_data = json.load(f)
class SocketIOHandler(logging.Handler):
    def __init__(self, socketio: "SocketIO", batch_time=1, *args, **kwargs):
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
        self.socketio.emit("log_message_batch", self.batch)
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

        @self.app.route("/paths", methods=["GET"])
        def get_paths():
            return jsonify({"paths": list(paths.keys())}), 200

        @self.app.route("/solo-fight", methods=["POST"])
        def solo_fight():
            if not request.is_json: 
                return jsonify({"error": "Request must be JSON"}), 400

            data = request.get_json()

            # Extracting the necessary information from the request
            account_id = data.get("accountId")
            character_id = data.get("characterId")
            path_id = data.get("pathId")
            
            try:
                monster_lvl_coef_diff = float(data.get("monsterLvlCoefDiff"))  # Explicitly convert to float
            except ValueError:
                return jsonify({"error": "Invalid format for monsterLvlCoefDiff. A float is required."}), 400

            # Placeholder for your logic to process the solo fight
            session = self.get_basic_session(account_id, character_id)
            session.type = SessionType.FIGHT
            session.path = json_to_path(paths[path_id])
            session.monsterLvlCoefDiff = monster_lvl_coef_diff
            # For example, validate the input and then update the database or process the game logic
            print(
                f"Processing solo fight for account {account_id}, character {character_id}, on path {path_id} with monster level coefficient difficulty {monster_lvl_coef_diff}"
            )

            self.start_bot_session(session, "solo-fight")

            # Responding with a success message or any other relevant information
            return jsonify({"message": "Solo fight initiated successfully"}), 200

        @self.app.route("/farm", methods=["GET"])
        def get_farm_data():
            farm_session_types = [SessionType.FARM, SessionType.MULTIPLE_PATHS_FARM]
            return jsonify({   
                "skills": list(dofus_data["skills"].values()),
                "paths": list(paths.keys()),
                "sessionTypes": [{"label": SessionType._VALUES_TO_NAMES[st], "value": st} for st in farm_session_types],
            }), 200

        @self.app.route("/farm", methods=["POST"])
        def farm():
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400

            data = request.get_json()
            print(f"Post request data: {data}")

            # Extracting the necessary information from the request
            account_id = data.get("accountId")
            character_id = data.get("characterId")
            session_type = data.get("type")
            path_id = data.get("pathId")
            paths_ids = data.get("pathsIds")
            job_filters = data.get("jobFilters")
            session = self.get_basic_session(account_id, character_id)
            session.type = session_type
            if session_type == SessionType.FARM:
                session.path = paths[path_id]
            elif session_type == SessionType.MULTIPLE_PATHS_FARM:
                session.pathsList = [json_to_path(paths[path_id]) for path_id in paths_ids]
            session.jobFilters = [JobFilter(job['jobId'], job['resoursesIds']) for job in job_filters]
            if path_id:
                session.path = json_to_path(paths[path_id])
            elif paths_ids:
                session.pathsList = [json_to_path(paths[path_id]) for path_id in paths_ids]
            self.start_bot_session(session, "solo-fight")

            # Responding with a success message or any other relevant information
            return jsonify({"message": "Solo fight initiated successfully"}), 200
        
        @self.app.route("/run/<account_id>/<character_id>/<action>")
        def run_action(account_id, character_id, action):
            try:
                session = self.get_basic_session(account_id, character_id)

                if action == "treasurehunt":
                    session.type = SessionType.TREASURE_HUNT
                    
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
                invManager = InventoryManager.getInstance(bot["obj"].name)
                if invManager and invManager.inventory:
                    bot_data["kamas"] = invManager.inventory.kamas
                if playermanager and playermanager.infos:
                    bot_data["level"] = playermanager.infos.level
                if playermanager and playermanager.inventoryWeightMax:
                    bot_data["pods"] = int(playermanager.inventoryWeight / playermanager.inventoryWeightMax * 100)
                result.append(bot_data)
            return jsonify(result)

        @self.app.route("/watch-log", methods=["POST"])
        def watch_log():
            data = request.json
            action = data["action"]

            if action == "start":
                bot_name = data["name"]
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

        @self.app.route("/import_accounts", methods=["GET"])
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
