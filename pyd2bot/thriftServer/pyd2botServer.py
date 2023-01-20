import json
import threading
from pyd2bot.apis.PlayerAPI import PlayerAPI
from pyd2bot.logic.common.frames.BotCharacterUpdatesFrame import BotCharacterUpdatesFrame
from pyd2bot.logic.common.frames.BotWorkflowFrame import BotWorkflowFrame
from pyd2bot.logic.managers.SessionManager import SessionManager, InactivityMonitor
from pyd2bot.logic.roleplay.frames.BotSellerCollectFrame import BotSellerCollectFrame
from pyd2bot.logic.roleplay.messages.LeaderPosMessage import LeaderPosMessage
from pyd2bot.logic.roleplay.messages.LeaderTransitionMessage import LeaderTransitionMessage
from pyd2bot.misc.Localizer import BankInfos
from pyd2bot.thriftServer.pyd2botService.ttypes import Character, Spell, DofusError
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEventsManager,
    KernelEvts,
)
from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import Breed
from pydofus2.com.ankamagames.dofus.datacenter.jobs.Skill import Skill
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import (
    InventoryManager,
)
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldPathFinder import (
    WorldPathFinder,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.DofusClient import DofusClient

lock = threading.Lock()


class Pyd2botServer:
    def __init__(self, id: str):
        self.id = id
        self.logger = Logger()

    def fetchUsedServers(self, token: str) -> list[dict]:
        try:
            DofusClient().login(token)
            servers = KernelEventsManager().wait(KernelEvts.SERVERS_LIST)
            if servers is None:
                raise DofusError(0, "Unable to fetch servers list.")
            DofusClient().shutdown()
            return json.dumps([server.to_json() for server in servers["used"]])
        except Exception as e:
            self.logger.error(f"[{self._id}] Error while reading socket. \n", exc_info=True)
            import sys
            import traceback

            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback_in_var = traceback.format_tb(exc_traceback)
            error_trace = "\n".join([str(e), str(exc_type), str(exc_value), "\n".join(traceback_in_var)])
            raise DofusError(0, error_trace)

    def fetchCharacters(self, token: str, serverId: int) -> list[Character]:
        result = list()
        DofusClient().login(token, serverId)
        charactersList = KernelEventsManager().wait(KernelEvts.CHARACTERS_LIST, 60)
        if charactersList is None:
            raise DofusError(code=0, message="Unable to fetch characters list.")
        for character in charactersList:
            chkwrgs = {
                "name": character.name,
                "id": character.id,
                "level": character.level,
                "breedId": character.breedId,
                "breedName": character.breed.name,
                "serverId": serverId,
                "serverName": PlayerManager().server.name,
            }
            result.append(Character(**chkwrgs))
        DofusClient().shutdown()
        return result

    def runSession(self, token: str, sessionJson: str) -> None:
        self.logger.debug(f"runSession called with token {token}")
        self.logger.debug("session: " + sessionJson)
        SessionManager().load(sessionJson)
        self.logger.debug("Session loaded")
        dofus2 = DofusClient()
        if SessionManager().type == "fight":
            dofus2.registerInitFrame(BotWorkflowFrame)
            dofus2.registerGameStartFrame(BotCharacterUpdatesFrame)
        elif SessionManager().type == "selling":
            pass
        else:
            raise DofusError("Unsupported session type: %s" % SessionManager().type)
        self.logger.debug("Frames registered")
        if token is None:
            raise DofusError("Unable to generate login token.")
        self.logger.debug(f"Generated LoginToken : {token}")
        serverId = SessionManager().character["serverId"]
        characId = SessionManager().character["id"]
        dofus2.login(token, serverId, characId)
        iam = InactivityMonitor()
        iam.start()

    def fetchBreedSpells(self, breedId: int) -> list["Spell"]:
        spells = []
        breed = Breed.getBreedById(breedId)
        if not breed:
            raise Exception(f"Breed {breedId} not found.")
        for spellVariant in breed.breedSpellVariants:
            for spellBreed in spellVariant.spells:
                spells.append(Spell(spellBreed.id, spellBreed.name))
        return spells

    def fetchJobsInfosJson(self) -> str:
        res = {}
        skills = Skill.getSkills()
        for skill in skills:
            if skill.gatheredRessource:
                if skill.parentJobId not in res:
                    res[skill.parentJobId] = {
                        "id": skill.parentJobId,
                        "name": skill.parentJob.name,
                        "gatheredRessources": [],
                    }
                gr = {
                    "name": skill.gatheredRessource.name,
                    "id": skill.gatheredRessource.id,
                    "levelMin": skill.levelMin,
                }
                if gr not in res[skill.parentJobId]["gatheredRessources"]:
                    res[skill.parentJobId]["gatheredRessources"].append(gr)
        return json.dumps(res)

    def moveToVertex(self, vertex: str):
        v = Vertex(**json.loads(vertex))
        self.logger.debug(f"Leader pos given, leader in vertex {v}.")
        Kernel().getWorker().process(LeaderPosMessage(v))

    def followTransition(self, transition: str):
        tr = Transition(**json.loads(transition))
        Kernel().getWorker().process(LeaderTransitionMessage(tr))
        print("LeaderTransitionMessage processed")

    def getStatus(self) -> str:
        status = PlayerAPI.status()
        print(f"get staus called -> Status: {status}")
        return status

    def comeToBankToCollectResources(self, bankInfos: str, guestInfos: str):
        with lock:
            bankInfos = BankInfos(**json.loads(bankInfos))
            guestInfos = json.loads(guestInfos)
            Kernel().getWorker().addFrame(BotSellerCollectFrame(bankInfos, guestInfos))

    def getCurrentVertex(self) -> str:
        return json.dumps(WorldPathFinder().currPlayerVertex.to_json())

    def getInventoryKamas(self) -> int:
        kamas = int(InventoryManager().inventory.kamas)
        return int(kamas)
