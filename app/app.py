import json
import logging
import os
import time
import sys
import traceback
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from marshmallow import ValidationError
from forms.schemas import FarmSessionSchema, FightSessionSchema
from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.models.session.models import JobFilter, Path, Session, SessionStatus, SessionType, UnloadType
from pydofus2.com.ankamagames.dofus.kernel.net.DisconnectionReasonEnum import DisconnectionReasonEnum
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import HtmlFormatter, Logger
import signal


def signal_handler(sig, frame):
    print("You pressed Ctrl+C or the server is reloading!")
    # Insert your cleanup code here
    for bot in BotManagerApp._running_bots.values():
        bot.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "Shutting down bot because of app shutdown")
        bot.join()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

paths_file = os.path.join(os.path.dirname(__file__), "db", "paths.json")
with open(paths_file, "r") as f:
    paths_json = json.load(f)
    paths: dict[str, Path] = {json_path["id"]: Path.from_dict(json_path) for json_path in paths_json}

staticdir = os.path.join(os.path.dirname(__file__), "static")
dofus_data_file = os.path.join(staticdir, "dofusData", "dofus_data.json")
with open(dofus_data_file, "r") as f:
    dofus_data = json.load(f)


class SocketIOHandler(logging.Handler):
    def __init__(self, socketio: "SocketIO", batch_time=0.6, *args, **kwargs):
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


def format_runtime(startTime, endTime=None):
    if not endTime:
        endTime = time.time()
    seconds = endTime - startTime
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
    _bots_run_infos = dict()
    _running_bots = dict[str, Pyd2Bot]()

    def __init__(self):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self._log_handler = None
        self.setup_routes()

    @staticmethod
    def get_basic_session(account_id: int, character_id: float, session_type: SessionType) -> Session:
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
            type=session_type,
        )

    def start_bot_session(self, session: Session):
        bot = Pyd2Bot(session)
        bot.addShutDownListener(self.on_bot_shutdown)
        self._running_bots[session.character.login] = bot
        self._bots_run_infos[session.character.login] = {
            "name": bot.name,
            "startTime": time.time(),
            "character": session.character.name,
            "activity": session.type.name,
            "kamas": "N/A",
            "level": "N/A",
            "pods": "N/A",
            "fights_count": 0,
            "earned_kamas": 0,
            "earned_levels": 0,
            "path_name": "N/A",
            "status": "Starting...",
            "runtime": "0s",
            "endTime": "N/A",
        }
        bot.start()

    def teardown(self, *args):
        for bot in self._running_bots.values():
            bot.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "Brutal shutdown because of app reload")
        self.socketio.stop()

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template(
                "index.html", accounts=AccountManager.get_accounts(), runningBots=self._bots_run_infos.values()
            )

        @self.app.route("/paths", methods=["GET"])
        def get_paths():
            return jsonify({"paths": [path for path in paths]}), 200

        @self.app.route("/solo-fight", methods=["POST"])
        def solo_fight():
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400
            print(f"Post request data: {request.get_json()}")
            try:
                data = FightSessionSchema().load(request.get_json())
            except ValidationError as err:
                return jsonify({"errors": err.messages}), 400
            account_id = data.get("accountId")
            character_id = data.get("characterId")
            path_id = data.get("pathId")
            session = self.get_basic_session(account_id, character_id, SessionType.FIGHT)
            # check if bot already running on this accounId
            if session.character.login in self._running_bots:
                return jsonify({"error": f"Bot already running for account {account_id}"}), 400
            session.monsterLvlCoefDiff = data.get("monsterLvlCoefDiff")
            session.path = paths[path_id]
            self.start_bot_session(session)
            return jsonify({"message": "Solo fight initiated successfully"}), 200

        @self.app.route("/farm", methods=["GET"])
        def get_farm_data():
            farm_session_types = [SessionType.FARM, SessionType.MULTIPLE_PATHS_FARM]
            return (
                jsonify(
                    {
                        "skills": list(dofus_data["skills"].values()),
                        "paths": [path.id for path in paths.values()],
                        "sessionTypes": [{"label": st.name, "value": st.value} for st in farm_session_types],
                    }
                ),
                200,
            )

        @self.app.route("/farm", methods=["POST"])
        def farm():
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400
            print(f"Post request data: {request.get_json()}")
            try:
                data = FarmSessionSchema().load(request.get_json())
            except ValidationError as err:
                return jsonify({"errors": err.messages}), 400
            account_id = data.get("accountId")
            character_id = data.get("characterId")
            session_type = data.get("type")
            path_id = data.get("pathId")
            paths_ids = data.get("pathsIds")
            job_filters = data.get("jobFilters")
            number_of_covers = data.get("number_of_covers")
            session = self.get_basic_session(account_id, character_id, session_type)
            # check if bot already running on this accounId
            if session.character.login in self._running_bots:
                return jsonify({"error": f"Bot already running for account {account_id}"}), 400
            session.type = session_type
            if session_type == SessionType.FARM:
                if path_id not in paths:
                    return jsonify({"error": f"Path {path_id} not found"}), 400
                session.path = paths[path_id]
            elif session_type == SessionType.MULTIPLE_PATHS_FARM:
                for path_id in paths_ids:
                    if path_id not in paths:
                        return jsonify({"error": f"Path {path_id} not found"}), 400
                session.number_of_covers = number_of_covers
                session.pathsList = [paths[path_id] for path_id in paths_ids]
            else:
                return jsonify({"error": f"Invalid session type: {session_type}"}), 400
            try:
                session.jobFilters = [JobFilter.from_dict(job) for job in job_filters]
            except Exception as e:
                return jsonify({"error": f"Invalid jobFilters: {e}"}), 400
            self.start_bot_session(session)

            return jsonify({"message": "Solo fight initiated successfully"}), 200

        @self.app.route("/treasurehunt/<account_id>/<character_id>")
        def trasurehunt(account_id, character_id):
            try:
                session = self.get_basic_session(account_id, character_id, SessionType.TREASURE_HUNT)
                self.start_bot_session(session)
            except Exception as e:
                return jsonify({"status": "error", "message": f"Error : {e}"})

            return jsonify({
                "status": "success",
                "message": f"Running treasurehunt for account {account_id}, character {character_id}",
            })

        @self.app.route("/stop/<botname>")
        def stop_action(botname):
            bot = self._running_bots.get(botname)
            if bot:
                bot.shutdown(DisconnectionReasonEnum.WANTED_SHUTDOWN, "User wanted to stop bot")
                bot.join()
                self._running_bots.pop(botname)
                # self._bots_run_infos.pop(botname)
            return jsonify({"status": "success", "message": f"Stopped bot {botname}"})

        @self.app.route("/get_running_bots")
        def get_running_bots():
            result = []
            for bot_oper in self._bots_run_infos.values():
                bot = self._running_bots.get(bot_oper["name"])
                if bot:
                    bot_status = bot.getState()
                    bot_oper["status"] = bot_status.name
                    stopped = bot_status in [SessionStatus.TERMINATED, SessionStatus.CRASHED, SessionStatus.BANNED]
                    if not stopped:
                        path = BotConfig.getInstance(bot_oper["name"]).curr_path
                        bot_oper["endTime"] = time.time()
                        bot_oper["runTime"] = format_runtime(bot_oper["startTime"], bot_oper.get("endTime", None))
                        bot_oper["path_name"] = path.name if path else "N/A"
                        bot_oper["fights_count"] = bot._nbrFightsDone
                        bot_oper["earned_kamas"] = bot._earnedKamas
                        bot_oper["earned_levels"] = bot._earnedLevels
                        playermanager = PlayedCharacterManager.getInstance(bot_oper["name"])
                        invManager = InventoryManager.getInstance(bot_oper["name"])
                        if invManager and invManager.inventory:
                            bot_oper["kamas"] = invManager.inventory.kamas
                        if playermanager and playermanager.infos:
                            bot_oper["level"] = playermanager.infos.level
                        if playermanager and playermanager.inventoryWeightMax:
                            bot_oper["pods"] = int(playermanager.inventoryWeight / playermanager.inventoryWeightMax * 100)
                else:
                    bot_oper["status"] = "Stopped"
                result.append(bot_oper)
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

    def on_bot_shutdown(self, login, reason, message):
        print(f"Bot {login} shutdown: {reason}\n{message}")
        # self._running_bots.pop(login)

    def run(self, debug=True, port=5000):
        self.socketio.run(self.app, debug=debug, port=port)


if __name__ == "__main__":
    bot_manager_app = BotManagerApp()
    bot_manager_app.run(debug=False)
