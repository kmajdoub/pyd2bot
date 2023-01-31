from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager, KernelEvts
from pydofus2.com.ankamagames.dofus.kernel.net.DisconnectionReasonEnum import DisconnectionReasonEnum
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from typing import TYPE_CHECKING
from pyd2bot.apis.PlayerAPI import PlayerAPI
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from pydofus2.com.ankamagames.dofus.datacenter.notifications.Notification import Notification
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.messages.FightRequestFailed import FightRequestFailed
from pydofus2.com.ankamagames.dofus.logic.game.fight.messages.MapMoveFailed import MapMoveFailed
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.messages.MovementRequestTimeoutMessage import MovementRequestTimeoutMessage
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldPathFinder import WorldPathFinder
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapMovementCancelMessage import (
    GameMapMovementCancelMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.notification.NotificationByServerMessage import (
    NotificationByServerMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapChangeFailedMessage import MapChangeFailedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapComplementaryInformationsDataMessage import (
    MapComplementaryInformationsDataMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapInformationsRequestMessage import (
    MapInformationsRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.interactive.InteractiveUsedMessage import InteractiveUsedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.interactive.InteractiveUseEndedMessage import (
    InteractiveUseEndedMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.interactive.InteractiveUseErrorMessage import (
    InteractiveUseErrorMessage,
)
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayGroupMonsterInformations import (
    GameRolePlayGroupMonsterInformations,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pyd2bot.apis.InventoryAPI import InventoryAPI
from pyd2bot.apis.MoveAPI import MoveAPI
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.frames.BotAutoTripFrame import BotAutoTripFrame
from pyd2bot.logic.roleplay.frames.BotPartyFrame import BotPartyFrame
from pyd2bot.logic.roleplay.messages.AutoTripEndedMessage import AutoTripEndedMessage
from pyd2bot.misc.BotEventsmanager import BotEventsManager
from pyd2bot.models.enums.ServerNotificationTitlesEnum import ServerNotificationTitlesEnum

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import RoleplayEntitiesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import RoleplayInteractivesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import RoleplayMovementFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayWorldFrame import RoleplayWorldFrame



class BotFarmPathFrame(Frame):
    
    def __init__(self, autoStart: bool = False):
        super().__init__()
        self._autoStart = autoStart
        self._followingIe = None
        self._usingInteractive = False
        self._followingMapchange = -1
        self._entities = dict()
        self._inAutoTrip = False
        self._discardedMonstersIds = []
        self._worker = Kernel().worker
        self._pulled = False
        self._followinMonsterGroup = None

    @property
    def farmPath(self):
        return BotConfig().path

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    @property
    def entitiesFrame(self) -> "RoleplayEntitiesFrame":
        return self._worker.getFrame("RoleplayEntitiesFrame")

    @property
    def interactivesFrame(self) -> "RoleplayInteractivesFrame":
        return self._worker.getFrame("RoleplayInteractivesFrame")

    @property
    def movementFrame(self) -> "RoleplayMovementFrame":
        return self._worker.getFrame("RoleplayMovementFrame")

    @property
    def partyFrame(self) -> "BotPartyFrame":
        return self._worker.getFrame("BotPartyFrame")

    @property
    def worldFrame(self) -> "RoleplayWorldFrame":
        return self._worker.getFrame("RoleplayWorldFrame")

    def pushed(self) -> bool:
        Logger().info("BotFarmPathFrame pushed")
        self._followinMonsterGroup = None
        if self._autoStart:
            KernelEventsManager().onceFramePushed("BotPartyFrame", self.doFarm)
        return True

    def pulled(self) -> bool:
        Logger().info("BotFarmPathFrame pulled")
        self._pulled = True
        if BotEventsManager().has_listeners(BotEventsManager.MEMBERS_READY):
            BotEventsManager().remove_listener(BotEventsManager.MEMBERS_READY, self.doFarm)
        self.reset()
        return True

    def reset(self):
        self._followingMapchange = None
        self._followingIe = None
        self._usingInteractive = False
        self._followinMonsterGroup = None
        self._inAutoTrip = False
        self._discardedMonstersIds.clear()
        if self.movementFrame:
            self.movementFrame._canMove = True
            self.movementFrame._followingMonsterGroup = None
            self.movementFrame._followingIe = None
            self.movementFrame._isRequestingMovement = False
            self.movementFrame._wantToChangeMap = None
            if self.movementFrame._requestFightTimeout:
                self.movementFrame._requestFightTimeout.cancel()
            self.movementFrame._requestFighFails = 0
            if self.movementFrame._changeMapTimeout:
                self.movementFrame._changeMapTimeout.cancel()
        if self.interactivesFrame:
            self.interactivesFrame.currentRequestedElementId = None
            self.interactivesFrame.usingInteractive = False

    @property
    def isInsideFarmPath(self) -> bool:
        return WorldPathFinder().currPlayerVertex in self.farmPath
    
    def process(self, msg: Message) -> bool:

        if isinstance(msg, AutoTripEndedMessage):
            self._inAutoTrip = False
            Logger().info("[BotFarmFrame] Auto trip ended calling doFarm")
            if msg.mapId is None:
                raise Exception("Auto trip was Unable to reach destination")
            self.doFarm()

        elif isinstance(msg, InteractiveUseErrorMessage):
            if self._inAutoTrip:
                return False
            Logger().error(
                f"[BotFarmFrame] Error unable to use interactive element '{msg.elemId}' with the skill '{msg.skillInstanceUid}'"
            )
            Logger().debug("*" * 80)
            self.reset()
            self.requestMapData()
            return True

        elif isinstance(msg, GameMapMovementCancelMessage):
            if self._followingIe:
                del self.interactivesFrame._ie[self._followingIe.element.elementId]
                del self.interactivesFrame._collectableIe[self._followingIe.element.elementId]
                self.reset()
                self.doFarm()
            return True

        elif isinstance(msg, (MapMoveFailed, MapChangeFailedMessage, MovementRequestTimeoutMessage)):
            ConnectionsHandler().closeConnection(DisconnectionReasonEnum.RESTARTING, "Restart due to Map change failed")

        elif isinstance(msg, FightRequestFailed):
            self._followinMonsterGroup = None
            self._discardedMonstersIds.append(int(msg.actorId))
            self.doFarm()
                
        elif isinstance(msg, InteractiveUsedMessage):
            if self._inAutoTrip:
                return False
            if PlayedCharacterManager().id == msg.entityId and msg.duration > 0:
                Logger().debug(f"[BotFarmFrame] Inventory weight {InventoryAPI.getWeightPercent():.2f}%")
                Logger().debug(f"[BotFarmFrame] Started using interactive element {msg.elemId} ....")
                if msg.duration > 0:
                    self._usingInteractive = True
            self._entities[msg.elemId] = msg.entityId
            return True

        elif isinstance(msg, InteractiveUseEndedMessage):
            if self._inAutoTrip:
                return False
            if self._entities[msg.elemId] == PlayedCharacterManager().id:
                self._followingIe = None
                self._usingInteractive = False
                Logger().debug(f"[BotFarmFrame] Interactive element {msg.elemId} use ended")
                Logger().debug("*" * 100)
                self.doFarm()
            del self._entities[msg.elemId]
            return True

        elif isinstance(msg, MapComplementaryInformationsDataMessage):
            if self._inAutoTrip:
                return False
            Logger().debug("-" * 100)
            self.reset()
            self.doFarm()
            return True

        elif isinstance(msg, NotificationByServerMessage):
            notification = Notification.getNotificationById(msg.id)
            if notification.titleId == ServerNotificationTitlesEnum.FULL_PODS:
                Logger().debug("[BotFarmFrame] Full pod reached will unload in bank")
                if not self._worker.contains("UnloadInBankFrame"):
                    raise Exception("Full pods but UnloadInBankFrame not found")
            return True

    def moveToNextStep(self):
        self._currTransition = next(self.farmPath)
        Logger().debug(
            f"[BotFarmFrame] Current Map {PlayedCharacterManager().currentMap.mapId} Moving to {self._currTransition.transitionMapId}"
        )
        MoveAPI.followTransition(self._currTransition,)
        if self.partyFrame:
            self.partyFrame.notifyFollowersWithTransition(self._currTransition)

    def attackMonsterGroup(self):
        availableMonsterFights = []
        currPlayerPos = PlayedCharacterManager().entity.position
        for entityId in self.entitiesFrame._monstersIds:
            if int(entityId) in self._discardedMonstersIds:
                continue
            infos: GameRolePlayGroupMonsterInformations = self.entitiesFrame.getEntityInfos(entityId)
            if self.insideCurrentPlayerZoneRp(infos.disposition.cellId):
                totalGrpLvl = infos.staticInfos.mainCreatureLightInfos.level + sum(
                    [ul.level for ul in infos.staticInfos.underlings]
                )
                if totalGrpLvl < BotConfig().monsterLvlCoefDiff * PlayedCharacterManager().limitedLevel:
                    monsterGroupPos = MapPoint.fromCellId(infos.disposition.cellId)
                    availableMonsterFights.append(
                        {"info": infos, "distance": currPlayerPos.distanceToCell(monsterGroupPos)}
                    )
        if availableMonsterFights:
            availableMonsterFights.sort(key=lambda x: x["distance"])
            entityId = availableMonsterFights[0]["info"].contextualId
            self._followinMonsterGroup = entityId
            self.movementFrame.attackMonsters(entityId)
            return
        Logger().debug("[BotFarmFrame] No monster group found")

    def insideCurrentPlayerZoneRp(self, cellId):
        tgtRpZone = MapDisplayManager().dataMap.cells[cellId].linkedZoneRP
        # Logger().debug(f"[BotFarmFrame] Current player zone {PlayedCharacterManager().currentZoneRp}, target zone {tgtRpZone}")
        return tgtRpZone == PlayedCharacterManager().currentZoneRp

    def doFarm(self, event=None):
        Logger().debug("[BotFarmFrame] doFarm called")
        if self._pulled:
            Logger().debug("[BotFarmFrame] Already pulled")
            return
        if PlayerAPI().status != "idle":
            Logger().debug(f"[BotFarmFrame] Can't farm, bot is not idle but '{PlayerAPI().status}'")
            return
        if WorldPathFinder().currPlayerVertex is None:
            Logger().debug("[BotFarmFrame] Can't farm, bot is still loading map")
            KernelEventsManager().once(KernelEvts.MAPPROCESSED, self.doFarm)
            return
        if WorldPathFinder().currPlayerVertex not in self.farmPath:
            Logger().debug(
                f"[BotFarmFrame] Map {WorldPathFinder().currPlayerVertex.mapId} not in farm path will switch to autotrip"
            )
            self._inAutoTrip = True
            self._worker.addFrame(BotAutoTripFrame(self.farmPath.startVertex.mapId))
            return
        if self.partyFrame:
            if not self.partyFrame.allMembersOnSameMap:
                Logger().debug("[BotFarmFrame] Waiting for party members to be on the same map")
                BotEventsManager().onAllPartyMembersShowed(self.doFarm)
                return
            else:
                Logger().debug("[BotFarmFrame] Waiting for party members to be idle")
                BotEventsManager().onAllPartyMembersIdle(self.doFarmEnsured)
                self.partyFrame.checkAllMembersIdle()
        else:
            self.doFarmEnsured()
    
    def doFarmEnsured(self):
        Logger().info("[BotFarmFrame] Party found and all members on the same map and are idle.")
        self._followinMonsterGroup = None
        self._followingIe = None
        if BotConfig().isFightSession:
            self.attackMonsterGroup()
        elif BotConfig().isFarmSession:
            self.collectResource()
        if self._followingIe is None and self._followinMonsterGroup is None:
            self.moveToNextStep()

    def requestMapData(self):
        mirmsg = MapInformationsRequestMessage()
        mirmsg.init(mapId_=MapDisplayManager().currentMapPoint.mapId)
        ConnectionsHandler().conn.send(mirmsg)

    def collectResource(self) -> None:
        target = None
        minDist = float("inf")
        for it in self.interactivesFrame.collectables.values():
            if it.enabled:
                if BotConfig().jobIds:
                    if it.skill.parentJobId not in BotConfig().jobIds:
                        continue
                    if PlayedCharacterManager().jobs[it.skill.parentJobId].jobLevel < it.skill.levelMin:
                        continue
                    if BotConfig().resourceIds:
                        if it.skill.gatheredRessource.id not in BotConfig().resourceIds:
                            continue
                ie = self.interactivesFrame.interactives.get(it.id)
                if not (self.interactivesFrame and self.interactivesFrame.usingInteractive):
                    playerEntity = PlayedCharacterManager().entity
                    if not playerEntity:
                        return
                    nearestCell, _ = self.worldFrame.getNearestCellToIe(ie.element, ie.position)
                    if self.insideCurrentPlayerZoneRp(nearestCell.cellId):
                        dist = PlayedCharacterManager().entity.position.distanceToCell(ie.position)
                        if dist < minDist:
                            target = ie
                            minDist = dist

        if target:
            self._followingIe = ie
            if minDist != 0:
                self.movementFrame.setFollowingInteraction(
                    {
                        "ie": ie.element,
                        "skillInstanceId": ie.skillUID,
                        "additionalParam": 0,
                    }
                )
                self.movementFrame.resetNextMoveMapChange()
                self.movementFrame.askMoveTo(nearestCell)
            else:
                self.movementFrame.activateSkill(ie.skillUID, ie.element.elementId, 0)
            Logger().info(f"[BotFarmFrame] Collecting {ie.element.elementId} ... skillId : {ie.skillUID}")
