import functools
import json
import sys
import threading
import traceback
from time import sleep

from pyd2bot.logic.roleplay.behaviors.movement.GetOutOfAnkarnam import \
    GetOutOfAnkarnam
from pyd2bot.logic.roleplay.behaviors.start.CreateNewCharacter import \
    CreateNewCharacter
from pyd2bot.logic.roleplay.behaviors.start.DeleteCharacter import \
    DeleteCharacter
from pyd2bot.SessionCtrl import SessionCtrl
from pyd2bot.thriftServer.pyd2botService.ttypes import (Breed, Character,
                                                        CharacterDetails,
                                                        D2BotError, RunSummary,
                                                        Server, Session, Spell,
                                                        Vertex)
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import \
    MapPosition
from pydofus2.com.ankamagames.dofus.internalDatacenter.connection.BasicCharacterWrapper import \
    BasicCharacterWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.actions.ChangeServerAction import \
    ChangeServerAction
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import \
    PlayerManager
from pydofus2.com.ankamagames.dofus.logic.connection.actions.ServerSelectionAction import \
    ServerSelectionAction
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import \
    InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.DofusClient import DofusClient


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
            if not isinstance(e, D2BotError):
                raise D2BotError(401, getTrace(e))
            else:
                raise e

    return wrapped


class Pyd2botServer:
    def __init__(self, id: str):
        self.id = id
        self.sessionsCtrl = None

    def ini_sessions_ctl(self):
        self.sessionsCtrl = SessionCtrl()

    @sendTrace
    def fetchUsedServers(self, token: str) -> list[Server]:
        from pydofus2.com.ankamagames.dofus.network.types.connection.GameServerInformations import \
            GameServerInformations

        Logger().debug("fetchUsedServers called with token: " + token)
        client = DofusClient("fetchServersThread")
        client._loginToken = token
        client._serverId = 0
        result = None
        client.start()
        KernelEventsManager.waitThreadRegister("fetchServersThread", 25)
        servers: dict[str, list[GameServerInformations]] = KernelEventsManager.getInstance("fetchServersThread").wait(
            KernelEvent.ServersList, 60
        )
        Logger().info(f"List servers: {[s.to_json() for s in servers['used']]}")
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
        client.shutdown()
        return result

    @sendTrace
    def fetchCharacters(self, token: str, session_id=None) -> list[Character]:
        from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import \
            PlayerManager

        instanceName = "fetchCharactersThread"
        result = list()
        client = DofusClient(instanceName)
        client.setLoginToken(token)
        client.sessionId = session_id
        client.start()
        evtsManager = KernelEventsManager.waitThreadRegister(instanceName, 25)
        evtsManager.wait(KernelEvent.ServersList, 60)
        first = True
        kernel = Kernel.waitThreadRegister(instanceName, 25)
        playerManager = PlayerManager.waitThreadRegister(instanceName, 25)
        for server in kernel.serverSelectionFrame.usedServers:
            if first:
                first = False
                kernel.worker.process(ServerSelectionAction.create(server.id))
            else:
                playerManager.charactersList.clear()
                kernel.worker.process(ChangeServerAction.create(server.id))
            evtsManager.wait(KernelEvent.CharactersList, 60)
            Logger().info(f"Server : {server.id}, List characters received")
            result += [
                Character(
                    character.name,
                    character.id,
                    character.level,
                    character.breedId,
                    character.breed.name,
                    playerManager.server.id,
                    playerManager.server.name,
                )
                for character in playerManager.charactersList
            ]
        client.shutdown()
        return result

    @sendTrace
    def deleteCharacter(self, token, serverId, characterId) -> bool:
        client = DofusClient(token)
        client._loginToken = token
        client._serverId = serverId
        client.start()
        stop = threading.Event()
        KernelEventsManager.waitThreadRegister(token, 25)

        def onCharacterDeleted(code, error):
            if error:
                stop.set()
                raise D2BotError(code, error)
            else:
                Logger().info("character deleted successfully")
                stop.set()

        def onCharactersList(event, return_value: list[BasicCharacterWrapper]):
            Logger().info("characters list received")
            if len(return_value) > 0 and any(c.id == characterId for c in return_value):
                DeleteCharacter().start(characterId, callback=onCharacterDeleted)
            else:
                stop.set()
                client.shutdown()
                raise D2BotError(0, "Character not found")

        KernelEventsManager.getInstance(token).once(KernelEvent.CharactersList, onCharactersList)
        stop.wait(220)
        client.shutdown()
        return True

    def createCharacter(self, token, serverId, name, breedId, sex, moveOutOfIncarnam) -> Character:
        client = DofusClient(token)
        client._loginToken = token
        client._serverId = serverId
        client.start()
        result = [None]
        KernelEventsManager.waitThreadRegister(token, 25)
        Logger().info("kernel event manager instance created")
        stop = threading.Event()

        def onCrash(evt, message="unknown", reason=None):
            client.shutdown(message, reason)
            stop.set()
            result[0] = D2BotError(1002, "Internal error")

        def onGetOutOfIncarnamEnded(code, error):
            if error:
                client.shutdown()
                stop.set()
                result[0] = D2BotError(code, error)
            else:
                Logger().info("Character now is in astrub")

        def onNewCharacterEnded(code, error, character: BasicCharacterWrapper = None):
            if error:
                Logger().error("Character cration failed for reason : " + str(error))
                client.shutdown()
                stop.set()
                result[0] = D2BotError(code, error)
            else:
                Logger().info("character created successfully")
                result[0] = Character(
                    character.name,
                    character.id,
                    character.level,
                    character.breedId,
                    character.breed.name,
                    PlayerManager.getInstance(token).server.id,
                    PlayerManager.getInstance(token).server.name,
                )
                if moveOutOfIncarnam:
                    GetOutOfAnkarnam().start(callback=onGetOutOfIncarnamEnded)
                else:
                    client.shutdown()
                    stop.set()

        def onCharactersList(event, return_value):
            Logger().info("characters list received")
            CreateNewCharacter().start(breedId, name, sex, callback=onNewCharacterEnded)

        KernelEventsManager.getInstance(token).once(KernelEvent.CharactersList, onCharactersList)
        KernelEventsManager.getInstance(token).once(KernelEvent.ClientCrashed, onCrash)
        Logger().info(f"Initialized account {token}")
        if not stop.wait(60):
            client.shutdown()
            raise D2BotError(403, "Request timedout")
        if isinstance(result[0], D2BotError):
            raise result[0]
        return result[0]

    @sendTrace
    def getBreeds(self) -> list[Breed]:
        from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import \
            Breed as dofusBreed
        from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
            BenchmarkTimer

        breeds = [Breed(b.id, b.name) for b in dofusBreed.getBreeds()]
        BenchmarkTimer.reset()
        Logger().info(f"Fetched breeds : {breeds}")
        return breeds

    @sendTrace
    def fetchCharacterDetails(self, token, serverId, characterId) -> CharacterDetails:
        client = DofusClient(token)
        client._loginToken = token
        client._serverId = serverId
        client._characterId = characterId
        stop = threading.Event()
        client.start()
        result = [None]

        def onCrash(evt, message="unknown", reason=None):
            client.shutdown(message, reason)
            result[0] = D2BotError(code=1002, message="Internal error")
            stop.set()

        def onMapProcessed():
            playerManager = PlayedCharacterManager.getInstance(token)
            inventory = InventoryManager.getInstance(token)
            mapPos = MapPosition.getMapPositionById(playerManager.currVertex.mapId)
            result[0] = CharacterDetails(
                playerManager.infos.level,
                playerManager.stats.getHealthPoints(),
                Vertex(playerManager.currVertex.mapId, playerManager.currVertex.zoneId),
                inventory.inventory.kamas,
                playerManager.currentSubArea.area.name,
                playerManager.currentSubArea.name,
                playerManager.currentCellId,
                mapPos.posX,
                mapPos.posY,
                playerManager.inventoryWeight,
                playerManager.shopWeight,
                playerManager.inventoryWeightMax,
            )
            client.shutdown()
            stop.set()

        KernelEventsManager.waitThreadRegister(token, 25)
        KernelEventsManager.getInstance(token).onceMapProcessed(onMapProcessed)
        KernelEventsManager.getInstance(token).once(KernelEvent.ClientCrashed, onCrash)
        if not stop.wait(30):
            client.shutdown()
            raise D2BotError(1003, "Request timed out")
        if client._crashed:
            raise D2BotError(403, client._shutDownMessage)
        if isinstance(result[0], D2BotError):
            raise result[0]
        return result[0]

    @sendTrace
    def getServers(self, token) -> list[Server]:
        from pydofus2.com.ankamagames.dofus.datacenter.servers.Server import \
            Server as dofusServer
        from pydofus2.com.ankamagames.dofus.network.types.connection.GameServerInformations import \
            GameServerInformations

        Logger().debug("fetchUsedServers called with token: " + token)
        client = DofusClient(token)
        client._loginToken = token
        client._serverId = 0
        result = None
        client.start()
        KernelEventsManager.waitThreadRegister(token, 25)
        servers: dict[str, list[GameServerInformations]] = KernelEventsManager.getInstance(token).wait(
            KernelEvent.ServersList, 60
        )
        Logger().info(f"List servers: {[s.to_json() for s in servers['all']]}")
        result = [
            Server(
                server.id,
                dofusServer.getServerById(server.id).name,
                server.status,
                server.completion,
                server.charactersCount,
                server.charactersSlots,
                server.date,
                server.isMonoAccount,
                server.isSelectable,
            )
            for server in servers["all"]
        ]
        client.shutdown()
        return result

    def fetchBreedSpells(self, breedId: int) -> list["Spell"]:
        from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import \
            Breed

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

    def addSession(self, session: Session) -> bool:
        return self.sessionsCtrl.addSession(session)

    @sendTrace
    def startSession(self, session: Session) -> bool:
        return self.sessionsCtrl.startSession(session)

    def stopSession(self, sessionId) -> bool:
        return self.sessionsCtrl.stopSession(sessionId)

    @sendTrace
    def getRunSummary(self) -> list[RunSummary]:
        return self.sessionsCtrl.getRunSummary()

    def getCharacterRunSummary(self, login) -> RunSummary:
        return self.sessionsCtrl.getCharacterRunSummary(login)

    @sendTrace
    def getSessionRunSummary(self, sessionId) -> list[RunSummary]:
        return self.sessionsCtrl.getSessionRunSummary(sessionId)

    def ping(self) -> str:
        return "pong"
