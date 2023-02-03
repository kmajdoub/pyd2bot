import threading
from queue import PriorityQueue
from time import perf_counter
from types import FunctionType
from typing import TYPE_CHECKING, Tuple
from pyd2bot.logic.fight.frames.BotFightTurnFrame import BotFightTurnFrame
from pyd2bot.logic.managers.BotConfig import BotConfig
from pydofus2.com.ankamagames.atouin.AtouinConstants import AtouinConstants
from pydofus2.com.ankamagames.atouin.messages.MapLoadedMessage import MapLoadedMessage
from pydofus2.com.ankamagames.atouin.utils.DataMapProvider import DataMapProvider
from pydofus2.com.ankamagames.dofus.datacenter.communication.InfoMessage import InfoMessage
from pydofus2.com.ankamagames.dofus.datacenter.effects.EffectInstance import EffectInstance
from pydofus2.com.ankamagames.dofus.internalDatacenter.spells.SpellWrapper import SpellWrapper
from pydofus2.com.ankamagames.dofus.internalDatacenter.stats.EntityStats import EntityStats
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightEntitiesFrame import FightEntitiesFrame
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.CurrentPlayedFighterManager import (
    CurrentPlayedFighterManager,
)
from pydofus2.com.ankamagames.dofus.logic.game.fight.miscs.FightReachableCellsMaker import FightReachableCellsMaker
from pydofus2.com.ankamagames.dofus.network.enums.FightOptionsEnum import FightOptionsEnum
from pydofus2.com.ankamagames.dofus.network.enums.TextInformationTypeEnum import TextInformationTypeEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightCastRequestMessage import (
    GameActionFightCastRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightNoSpellCastMessage import (
    GameActionFightNoSpellCastMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.sequence.SequenceEndMessage import SequenceEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.sequence.SequenceStartMessage import (
    SequenceStartMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.basic.TextInformationMessage import TextInformationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.character.GameFightShowFighterMessage import (
    GameFightShowFighterMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightEndMessage import GameFightEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightJoinMessage import (
    GameFightJoinMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightOptionToggleMessage import (
    GameFightOptionToggleMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightReadyMessage import (
    GameFightReadyMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnResumeMessage import (
    GameFightTurnResumeMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartPlayingMessage import (
    GameFightTurnStartPlayingMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapComplementaryInformationsDataMessage import (
    MapComplementaryInformationsDataMessage,
)
from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.GameFightMonsterInformations import (
    GameFightMonsterInformations,
)
from pydofus2.com.ankamagames.dofus.network.types.game.context.GameContextActorInformations import (
    GameContextActorInformations,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.map.LosDetector import LosDetector
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.jerakine.types.zones.Cross import Cross
from pydofus2.com.ankamagames.jerakine.types.zones.IZone import IZone
from pydofus2.com.ankamagames.jerakine.types.zones.Lozenge import Lozenge
from pydofus2.com.ankamagames.jerakine.utils.display.spellZone.SpellShapeEnum import SpellShapeEnum
from pydofus2.damageCalculation.tools.StatIds import StatIds
from pydofus2.mapTools import MapTools

lock = threading.Lock()
if TYPE_CHECKING:
    from pyd2bot.logic.roleplay.frames.BotPartyFrame import BotPartyFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightBattleFrame import FightBattleFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightContextFrame import FightContextFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightTurnFrame import FightTurnFrame


class Target:
    def __init__(self, entityId: float, pos: MapPoint) -> None:
        self.pos: MapPoint = pos
        self.entityId = entityId

    def __str__(self) -> str:
        return f"({self.entityId} at {self.pos.cellId})"


class BotFightFrame(Frame):
    VERBOSE = True
    ACTION_TIMEOUT = 7
    _average_time_to_find_path = 0
    _number_of_path_calculations = 0
    _total_time_to_find_path = 0

    def __init__(self):
        self._turnAction = list[FunctionType]()
        self._botTurnFrame = BotFightTurnFrame()
        self.spellId = BotConfig().primarySpellId
        self._spellCastFails = 0
        self._inFight = False
        self._fightCount: int = 0
        self._lastTarget: int = None
        self._spellw: SpellWrapper = None
        self._spellShape = None
        self._currentPath = None
        self._currentTarget = None
        super().__init__()

    def pushed(self) -> bool:
        self._turnAction = list[FunctionType]()
        self._botTurnFrame = BotFightTurnFrame()
        self.spellId = BotConfig().primarySpellId
        self._inFight = False
        self._lastTarget: int = None
        self._spellw: SpellWrapper = None
        self._myTurn = False
        self._wantcastSpell = None
        self._reachableCells = None
        self._seqQueue = []
        self._waitingSeqEnd = False
        self._turnPlayed = 0
        self._spellCastFails = 0
        Kernel().worker.addFrame(self._botTurnFrame)
        return True

    @property
    def turnFrame(self) -> "FightTurnFrame":
        return Kernel().worker.getFrame("FightTurnFrame")

    @property
    def fightContextFrame(self) -> "FightContextFrame":
        return Kernel().worker.getFrame("FightContextFrame")

    @property
    def entitiesFrame(self) -> "FightEntitiesFrame":
        return Kernel().worker.getFrame("FightEntitiesFrame")

    @property
    def battleFrame(self) -> "FightBattleFrame":
        return Kernel().worker.getFrame("FightBattleFrame")

    @property
    def partyFrame(self) -> "BotPartyFrame":
        return Kernel().worker.getFrame("BotPartyFrame")

    def pulled(self) -> bool:
        self._spellw = None
        if self._reachableCells:
            self._reachableCells.clear()
        self._turnAction.clear()
        Kernel().worker.removeFrame(self._botTurnFrame)
        return True

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    @property
    def fightCount(self) -> int:
        return self._fightCount

    def buildPath(self, parentOfcell: dict[int, int], endCellId):
        path = [endCellId]
        currCellId = endCellId
        while True:
            currCellId = parentOfcell.get(currCellId)
            if currCellId is None:
                break
            path.append(currCellId)
        path.reverse()
        return path

    def findCellsWithLosToTargets(self, spellw: SpellWrapper, targets: list[Target]) -> list[int]:
        LosDetector.clearCache()
        hasLosToTargets = dict[int, list]()
        spellZone = self.getSpellZone(spellw)
        maxRangeFromFighter = 0
        for target in targets:
            currSpellZone = spellZone.getCells(target.pos.cellId)
            los = LosDetector.getCells(DataMapProvider(), currSpellZone, target.pos.cellId)
            for cellId in los:
                if cellId not in hasLosToTargets:
                    hasLosToTargets[cellId] = list[Target]()
                hasLosToTargets[cellId].append(target)
                maxRangeFromFighter = max(maxRangeFromFighter, MapTools.getDistance(self.fighterPos.cellId, cellId))
        return maxRangeFromFighter, hasLosToTargets

    def findPathToTarget(self, spellw: SpellWrapper, targets: list[Target]) -> Tuple[Target, list[int]]:
        if not targets:
            return None, None
        for target in targets:
            if target.pos.distanceTo(self.fighterPos) <= 1:
                return target, []
        maxRangeFromFighter, hasLosToTargets = self.findCellsWithLosToTargets(spellw, targets)
        if not hasLosToTargets:
            return None, None
        if self.fighterPos.cellId in hasLosToTargets:
            return hasLosToTargets[self.fighterPos.cellId][0], []
        if self.movementPoints <= 0:
            return None, None
        reachableCells = set(
            FightReachableCellsMaker(self.fighterInfos, self.fighterPos.cellId, maxRangeFromFighter).reachableCells
        )
        queue = PriorityQueue[Tuple[int, int, int]]()
        queue.put((0, 0, self.fighterPos.cellId))
        visited = set()
        parentOfCell = {}
        bestAlternative = None
        BtestAlternativeCost = float("inf")
        while not queue.empty():
            _, usedPms, currCellId = queue.get()
            if currCellId in visited:
                continue
            visited.add(currCellId)
            currPoint = MapPoint.fromCellId(currCellId)
            for nextMapPoint in currPoint.vicinity():
                nextCellId = nextMapPoint.cellId
                if nextCellId not in visited and nextCellId in reachableCells:
                    parentOfCell[nextCellId] = currCellId
                    if nextCellId in hasLosToTargets:
                        path = self.buildPath(parentOfCell, nextCellId)
                        return hasLosToTargets[nextCellId][0], path[1:]
                    heuristic = (
                        usedPms
                        + 1
                        + 10 * min([MapTools.getDistance(nextCellId, cellId) for cellId in hasLosToTargets])
                    )
                    if heuristic < BtestAlternativeCost:
                        bestAlternative = nextCellId
                        BtestAlternativeCost = heuristic
                    queue.put((heuristic, usedPms + 1, nextCellId))
        path = self.buildPath(parentOfCell, bestAlternative)
        return None, path[1:]

    @classmethod
    def updateAveragePathTime(cls, time: float):
        with lock:
            cls._total_time_to_find_path += time
            cls._number_of_path_calculations += 1
            cls._average_time_to_find_path = cls._total_time_to_find_path / cls._number_of_path_calculations
            if cls._number_of_path_calculations > 100:
                cls._total_time_to_find_path = 0
                cls._number_of_path_calculations = 0

    def onInvisibleMobBlockingWay(self):
        self._turnAction.clear()
        self.addTurnAction(self.turnEnd, [])
        self.nextTurnAction()

    def playTurn(self):
        targets = self.getTargetableEntities(self.spellw, targetSum=False)
        if not targets:
            targets = self.getTargetableEntities(self.spellw, targetSum=True)
            if not targets:
                self.addTurnAction(self.turnEnd, [])
                self.nextTurnAction()
                return
        Logger().info(f"[FightAlgo] MP : {self.movementPoints}, AP : {self.actionPoints}")
        Logger().info(f"[FightAlgo] Current attack spell : {self.spellw.spell.name}")
        target, path = self.findPathToTarget(self.spellw, targets)
        if path is not None:
            self._currentPath = path
            self._currentTarget = target
            if len(path) <= self.movementPoints:
                if path:
                    self.addTurnAction(self.askMove, [path])
                if target:
                    self.addTurnAction(self.castSpell, [self.spellId, target.pos.cellId])
                if not target and not path:
                    self.addTurnAction(self.turnEnd, [])
            else:
                self.addTurnAction(self.askMove, [path[: int(self.movementPoints)]])
                self.addTurnAction(self.turnEnd, [])
        else:
            self.addTurnAction(self.turnEnd, [])
        self.nextTurnAction()

    @property
    def spellw(self) -> SpellWrapper:
        if self._spellw is None:
            for spellw in PlayedCharacterManager().playerSpellList:
                if spellw.id == self.spellId:
                    self._spellw = spellw
        return self._spellw

    def getActualSpellRange(self, spellw: SpellWrapper) -> int:
        playerStats: EntityStats = CurrentPlayedFighterManager().getStats()
        range: int = spellw["range"]
        minRange: int = spellw["minRange"]
        if spellw["rangeCanBeBoosted"]:
            range += playerStats.getStatTotalValue(StatIds.RANGE) - playerStats.getStatAdditionalValue(StatIds.RANGE)
        range = max(min(max(minRange, range), AtouinConstants.MAP_WIDTH * AtouinConstants.MAP_HEIGHT), 0)
        return range

    def getSpellShape(self, spellw: SpellWrapper) -> int:
        if not self._spellShape:
            self._spellShape = 0
            spellEffect: EffectInstance = None
            for spellEffect in spellw["effects"]:
                if spellEffect.zoneShape != 0 and (
                    spellEffect.zoneSize > 0
                    or spellEffect.zoneSize == 0
                    and (spellEffect.zoneShape == SpellShapeEnum.P or spellEffect.zoneMinSize < 0)
                ):
                    self._spellShape = spellEffect.zoneShape
                    break
        return self._spellShape

    def getSpellZone(self, spellw: SpellWrapper) -> IZone:
        range: int = self.getActualSpellRange(spellw)
        minRange: int = spellw.minimalRange
        spellShape: int = self.getSpellShape(spellw)
        castInLine: bool = spellw["castInLine"] or spellShape == SpellShapeEnum.l
        if castInLine:
            if spellw["castInDiagonal"]:
                shapePlus = Cross(minRange, range, DataMapProvider())
                shapePlus.allDirections = True
                return shapePlus
            return Cross(minRange, range, DataMapProvider())
        elif spellw["castInDiagonal"]:
            shapePlus = Cross(minRange, range, DataMapProvider())
            shapePlus.diagonal = True
            return shapePlus
        else:
            return Lozenge(minRange, range, DataMapProvider())

    def addTurnAction(self, fct: FunctionType, args: list) -> None:
        self._turnAction.append({"fct": fct, "args": args})

    def nextTurnAction(self) -> None:
        if not self.battleFrame:
            Logger().warning("[FightAlgo] No battle frame found")
            return
        if self.battleFrame._executingSequence:
            if self.VERBOSE:
                Logger().warn(f"[FightBot] Battle is busy processing sequences")
            Kernel().worker.terminated.wait(1)
            self.nextTurnAction()
            return
        else:
            if self.VERBOSE:
                Logger().debug(f"[FightBot] Next turn actions, {[a['fct'].__name__ for a in self._turnAction]}")
            if len(self._turnAction) > 0:
                action = self._turnAction.pop(0)
                self._waitingSeqEnd = True
                action["fct"](*action["args"])
            else:
                self.playTurn()

    def updateReachableCells(self) -> None:
        self._reachableCells = FightReachableCellsMaker(self.fighterInfos).reachableCells

    def canCastSpell(self, spellw: SpellWrapper, targetId: int) -> bool:
        reason = [""]
        if CurrentPlayedFighterManager().canCastThisSpell(self.spellId, spellw.spellLevel, targetId, reason):
            return True
        else:
            return False

    def process(self, msg: Message) -> bool:

        if isinstance(msg, GameFightJoinMessage):
            Logger().debug(f"****************** Joined fight ******************************************")
            BotConfig().lastFightTime = perf_counter()
            self._fightCount += 1
            self._spellCastFails = 0
            self._inFight = True
            if BotConfig().isLeader and not BotConfig().fightOptionsSent:
                gfotmsg = GameFightOptionToggleMessage()
                gfotmsg.init(FightOptionsEnum.FIGHT_OPTION_SET_SECRET)
                ConnectionsHandler().send(gfotmsg)
                Kernel(0.3)
                gfotmsg = GameFightOptionToggleMessage()
                gfotmsg.init(FightOptionsEnum.FIGHT_OPTION_SET_TO_PARTY_ONLY)
                ConnectionsHandler().send(gfotmsg)
                BotConfig().fightOptionsSent = True
            return False

        elif isinstance(msg, GameFightEndMessage):
            self._inFight = False
            Logger().debug(f"Average time to calculate path to target: {self._average_time_to_find_path}")
            return True

        elif isinstance(msg, GameActionFightNoSpellCastMessage):
            if self.VERBOSE:
                Logger().debug(f"[FightBot] Failed to cast spell")
            if self._spellCastFails > 2:
                self.turnEnd()
                return True
            self._spellCastFails += 1
            self.playTurn()
            return True

        elif isinstance(msg, MapComplementaryInformationsDataMessage):
            self._wait = False
            return False

        elif isinstance(msg, MapLoadedMessage):
            self._wait = True
            return False

        elif isinstance(msg, GameFightShowFighterMessage):
            msg.informations.contextualId
            self._turnPlayed = 0
            self._myTurn = False
            if self.partyFrame and self.partyFrame.isLeader:
                for memberId in self.partyFrame.partyMembers:
                    if not self.entitiesFrame.getEntityInfos(memberId):
                        return True
            startFightMsg = GameFightReadyMessage()
            startFightMsg.init(True)
            ConnectionsHandler().send(startFightMsg)
            return True

        elif isinstance(msg, SequenceEndMessage):
            if self._myTurn:
                if self._seqQueue:
                    self._seqQueue.pop()
                    if not self._seqQueue:
                        if self._waitingSeqEnd:
                            self._waitingSeqEnd = False
                            if self._inFight:
                                self.nextTurnAction()
            return True

        elif isinstance(msg, SequenceStartMessage):
            if self._myTurn:
                self._seqQueue.append(msg)
            return True

        elif isinstance(msg, (GameFightTurnStartPlayingMessage, GameFightTurnResumeMessage)):
            if self._botTurnFrame._myTurn:
                if self.VERBOSE:
                    Logger().debug("******************** bot turn to play *********************************")
                self._spellCastFails = 0
                self._seqQueue.clear()
                self._myTurn = True
                self._turnAction.clear()
                self._turnPlayed += 1
                self._tryWithLessRangeOf = 0
                self.nextTurnAction()
            return True

        elif isinstance(msg, TextInformationMessage):
            msgInfo = InfoMessage.getInfoMessageById(msg.msgType * 10000 + msg.msgId)
            if msgInfo:
                textId = msgInfo.textId
            else:
                if msg.msgType == TextInformationTypeEnum.TEXT_INFORMATION_ERROR:
                    textId = InfoMessage.getInfoMessageById(10231).textId
                else:
                    textId = InfoMessage.getInfoMessageById(207).textId
            if textId == 4993:  # Wants to use more than the pms available
                self.turnEnd()
            if textId == 4897:
                self.onInvisibleMobBlockingWay()
            return True

        return False

    @property
    def actionPoints(self) -> int:
        stats = CurrentPlayedFighterManager().getStats()
        return stats.getStatTotalValue(StatIds.ACTION_POINTS)

    @property
    def movementPoints(self) -> int:
        stats = CurrentPlayedFighterManager().getStats()
        return stats.getStatTotalValue(StatIds.MOVEMENT_POINTS)

    def turnEnd(self) -> None:
        self._spellCastFails = 0
        self._myTurn = False
        self._seqQueue.clear()
        self._turnAction.clear()
        if self.turnFrame:
            self.turnFrame.finishTurn()

    @property
    def fighterInfos(self) -> "GameContextActorInformations":
        info = self.entitiesFrame.getEntityInfos(CurrentPlayedFighterManager().currentFighterId)
        return info

    @property
    def fighterPos(self) -> "MapPoint":
        return MapPoint.fromCellId(self.fighterInfos.disposition.cellId)

    def getTargetableEntities(self, spellw: SpellWrapper, targetSum=False) -> list[Target]:
        result = list[Target]()
        if not FightEntitiesFrame.getCurrentInstance() or not self.battleFrame:
            return []
        if self.fighterInfos is None:
            return []
        for entity in FightEntitiesFrame.getCurrentInstance().entities.values():
            if entity.contextualId < 0 and isinstance(entity, GameFightMonsterInformations):
                monster = entity
                if (
                    monster.spawnInfo.teamId != self.fighterInfos.spawnInfo.teamId
                    and float(entity.contextualId) not in self.battleFrame._deadTurnsList
                    and (targetSum or not monster.stats.summoned)
                    and self.canCastSpell(spellw, entity.contextualId)
                    and entity.disposition.cellId != -1
                ):
                    result.append(Target(entity.contextualId, MapPoint.fromCellId(entity.disposition.cellId)))
        if self.VERBOSE:
            Logger().debug(f"[FightBot] Found targets : {[str(tgt) for tgt in result]}")
        return result

    def castSpell(self, spellId: int, cellId: bool) -> None:
        if self.VERBOSE:
            Logger().debug(f"[FightBot] Casting spell {spellId} on cell {cellId}.")
        gafcrmsg: GameActionFightCastRequestMessage = GameActionFightCastRequestMessage()
        gafcrmsg.init(spellId, cellId)
        ConnectionsHandler().send(gafcrmsg)

    def askMove(self, cells: list[int], cellsTackled: list[int] = []) -> None:
        if cells is None or len(cells) == 0:
            Logger().error("cells input invalid", exec_info=True)
        if self.VERBOSE:
            Logger().debug(f"[FightBot] Ask move follwing path {cells}.")
        if not self._myTurn:
            Logger().warn("[FightBot] Wants to move when it's not its turn yet.")
            return False
        fightTurnFrame: "FightTurnFrame" = Kernel().worker.getFrame("FightTurnFrame")
        if not fightTurnFrame:
            Logger().warn("[FightBot] Wants to move inside fight but 'FightTurnFrame' not found in kernel.")
            return False
        fightTurnFrame.askMoveTo(cells, cellsTackled)
        return True
