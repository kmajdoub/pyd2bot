import json
import threading
from pyd2bot.logic.common.frames.BotCharacterUpdatesFrame import BotCharacterUpdatesFrame
from pyd2bot.logic.common.frames.BotWorkflowFrame import BotWorkflowFrame
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.thriftServer.pyd2botService.ttypes import (
    Character,
    Spell,
    DofusError,
    Server,
    Session,
    SessionType,
)
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEventsManager,
    KernelEvent,
)
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import (
    InventoryManager,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.DofusClient import DofusClient
import sys
import traceback
import functools


def getTrace(e):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback_in_var = traceback.format_tb(exc_traceback)
    error_trace = "\n".join([str(e), str(exc_type), str(exc_value), "\n".join(traceback_in_var)])
    return error_trace


lock = threading.Lock()


def sendTrace(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise DofusError(0, getTrace(e))

    return wrapped


class Pyd2botServer:
    def __init__(self, id: str):
        self.id = id
        self.

    @sendTrace
    def fetchUsedServers(self, token: str) -> list[Server]:
        from pydofus2.com.ankamagames.dofus.network.types.connection.GameServerInformations import (
            GameServerInformations,
        )
        self.Logger().debug("fetchUsedServers called with token: " + token)
        DofusClient().login(token)
        servers: dict[str, list[GameServerInformations]] = KernelEventsManager().wait(KernelEvent.SERVERS_LIST, 60)
        self.Logger().info(f"list servers: {[s.to_json() for s in servers['used']]}")
        result = [
            Server(
                server.id,
                server.status,
                server.completion,
                server.charactersCount,
                server.charactersSlots,
                server.date,
                server.isMonoAccount,
                server.isSelectable,
            )
            for server in servers["used"]
        ]
        DofusClient().shutdown()
        return result

    @sendTrace
    def fetchCharacters(self, token: str, serverId: int) -> list[Character]:
        from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
        from pydofus2.com.ankamagames.dofus.internalDatacenter.connection.BasicCharacterWrapper import (
            BasicCharacterWrapper,
        )

        result = list()
        DofusClient().login(token, serverId)
        charactersList: list[BasicCharacterWrapper] = KernelEventsManager().wait(KernelEvent.CHARACTERS_LIST, 60)
        if charactersList is None:
            raise Exception("Timeout!")
        result = [
            Character(
                character.name,
                character.id,
                character.level,
                character.breedId,
                character.breed.name,
                serverId,
                PlayerManager().server.name,
            )
            for character in charactersList
        ]
        DofusClient().shutdown()
        return result

    @sendTrace
    def runSession(self, token: str, session: Session) -> None:
        if session.type == SessionType.FIGHT:
            BotConfig().initFromSession(session, "leader")
            DofusClient().registerInitFrame(BotWorkflowFrame)
            DofusClient().registerGameStartFrame(BotCharacterUpdatesFrame)
            serverId = session.leader.serverId
            characId = session.leader.id
            DofusClient().login(token, serverId, characId)
            for character in session.followers:
                BotConfig().initFromSession(session, "follower", character)
        else:
            raise Exception(f"Unsupported session type: {session.type}")

    def fetchBreedSpells(self, breedId: int) -> list["Spell"]:
        from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import Breed

        spells = []
        breed = Breed.getBreedById(breedId)
        if not breed:
            raise Exception(f"Breed {breedId} not found.")
        for spellVariant in breed.breedSpellVariants:
            for spellBreed in spellVariant.spells:
                spells.append(Spell(spellBreed.id, spellBreed.name))
        return spells

    def fetchJobsInfosJson(self) -> str:
        from pydofus2.com.ankamagames.dofus.datacenter.jobs.Skill import Skill

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
        from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
        from pyd2bot.logic.roleplay.messages.LeaderPosMessage import LeaderPosMessage

        v = Vertex(**json.loads(vertex))
        self.Logger().debug(f"Leader pos given, leader in vertex {v}.")
        Kernel().worker.process(LeaderPosMessage(v))

    def followTransition(self, transition: str):
        from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import (
            Transition,
        )
        from pyd2bot.logic.roleplay.messages.LeaderTransitionMessage import LeaderTransitionMessage

        tr = Transition(**json.loads(transition))
        Kernel().worker.process(LeaderTransitionMessage(tr))
        print("LeaderTransitionMessage processed")

    def getStatus(self) -> str:
        from pyd2bot.apis.PlayerAPI import PlayerAPI

        status = PlayerAPI().status
        print(f"get staus called -> Status: {status}")
        return status

    def comeToBankToCollectResources(self, bankInfos: str, guestInfos: str):
        from pyd2bot.misc.Localizer import BankInfos
        from pyd2bot.logic.roleplay.frames.BotSellerCollectFrame import BotSellerCollectFrame

        with lock:
            bankInfos = BankInfos(**json.loads(bankInfos))
            guestInfos = json.loads(guestInfos)
            Kernel().worker.addFrame(BotSellerCollectFrame(bankInfos, guestInfos))

    def getCurrentVertex(self) -> str:
        from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldPathFinder import (
            WorldPathFinder,
        )
        return json.dumps(WorldPathFinder().currPlayerVertex.to_json())

    def getInventoryKamas(self) -> int:
        kamas = int(InventoryManager().inventory.kamas)
        return int(kamas)
