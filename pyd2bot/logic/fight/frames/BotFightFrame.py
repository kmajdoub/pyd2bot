import threading
from queue import PriorityQueue
from time import perf_counter
from types import FunctionType
from typing import TYPE_CHECKING, Tuple

from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.misc.BotEventsmanager import BotEventsManager
from pydofus2.com.ankamagames.atouin.AtouinConstants import AtouinConstants
from pydofus2.com.ankamagames.atouin.messages.MapLoadedMessage import \
    MapLoadedMessage
from pydofus2.com.ankamagames.atouin.utils.DataMapProvider import \
    DataMapProvider
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.datacenter.communication.InfoMessage import \
    InfoMessage
from pydofus2.com.ankamagames.dofus.datacenter.effects.EffectInstance import \
    EffectInstance
from pydofus2.com.ankamagames.dofus.internalDatacenter.spells.SpellWrapper import \
    SpellWrapper
from pydofus2.com.ankamagames.dofus.internalDatacenter.stats.EntityStats import \
    EntityStats
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.common.managers.StatsManager import \
    StatsManager
from pydofus2.com.ankamagames.dofus.logic.game.common.frames.SpellInventoryManagementFrame import \
    SpellInventoryManagementFrame
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightEntitiesFrame import \
    FightEntitiesFrame
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.BuffManager import \
    BuffManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.CurrentPlayedFighterManager import \
    CurrentPlayedFighterManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.miscs.FightReachableCellsMaker import \
    FightReachableCellsMaker
from pydofus2.com.ankamagames.dofus.network.enums.FightOptionsEnum import \
    FightOptionsEnum
from pydofus2.com.ankamagames.dofus.network.enums.TextInformationTypeEnum import \
    TextInformationTypeEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightCastRequestMessage import \
    GameActionFightCastRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightNoSpellCastMessage import \
    GameActionFightNoSpellCastMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.sequence.SequenceEndMessage import \
    SequenceEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.sequence.SequenceStartMessage import \
    SequenceStartMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.basic.TextInformationMessage import \
    TextInformationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.character.GameFightShowFighterMessage import \
    GameFightShowFighterMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightEndMessage import \
    GameFightEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightJoinMessage import \
    GameFightJoinMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightOptionStateUpdateMessage import \
    GameFightOptionStateUpdateMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightOptionToggleMessage import \
    GameFightOptionToggleMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightReadyMessage import \
    GameFightReadyMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnEndMessage import \
    GameFightTurnEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnFinishMessage import \
    GameFightTurnFinishMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnReadyMessage import \
    GameFightTurnReadyMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnReadyRequestMessage import \
    GameFightTurnReadyRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnResumeMessage import \
    GameFightTurnResumeMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartMessage import \
    GameFightTurnStartMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartPlayingMessage import \
    GameFightTurnStartPlayingMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapMovementRequestMessage import \
    GameMapMovementRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapNoMovementMessage import \
    GameMapNoMovementMessage
from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.GameFightFighterInformations import \
    GameFightFighterInformations
from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.GameFightMonsterInformations import \
    GameFightMonsterInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.map.LosDetector import LosDetector
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.jerakine.types.positions.MovementPath import \
    MovementPath
from pydofus2.com.ankamagames.jerakine.types.zones.Cross import Cross
from pydofus2.com.ankamagames.jerakine.types.zones.IZone import IZone
from pydofus2.com.ankamagames.jerakine.types.zones.Lozenge import Lozenge
from pydofus2.com.ankamagames.jerakine.utils.display.spellZone.SpellShapeEnum import \
    SpellShapeEnum
from pydofus2.damageCalculation.tools.StatIds import StatIds
from pydofus2.mapTools import MapTools

lock = threading.Lock()
if TYPE_CHECKING:
    from pyd2bot.logic.roleplay.frames.BotPartyFrame import BotPartyFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightBattleFrame import \
        FightBattleFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightContextFrame import \
        FightContextFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightTurnFrame import \
        FightTurnFrame

class Target:
    
    def __init__(self, entity: GameFightMonsterInformations, cellId: int) -> None:
        self.entity = entity
        self.pos = MapPoint.fromCellId(entity.disposition.cellId)
        self.entityId = entity.contextualId
        self.distFromPlayer = self.pos.distanceToCellId(cellId)

    def __str__(self) -> str:
        return f"({self.entity.contextualId}, { self.entity.disposition.cellId}, {self.distFromPlayer})"

class BotFightFrame(Frame):
    VERBOSE = True
    ACTION_TIMEOUT = 7
    CONSECUTIVE_MOVEMENT_DELAY: int = 0.25
    _average_time_to_find_path = 0
    _number_of_path_calculations = 0
    _total_time_to_find_path = 0

    def __init__(self):
        self.init()
        super().__init__()

    def init(self):
        self._turnAction = list[FunctionType]()
        self._spellCastFails = 0
        self._inFight = False
        self._fightCount: int = 0
        self._lastTarget: int = None
        self._spellw: SpellWrapper = None
        self._spellShape = None
        self._myTurn = False
        self._currentPath = None
        self._currentTarget = None
        self._wantcastSpell = None
        self.currentPlayer = None
        self._lastPlayerId = None
        self.spellw = None
        self._reachableCells = None
        self._seqQueue = []
        self._waitingSeqEnd = False
        self._turnPlayed = 0
        self._isRequestingMovement = False
        self._requestingCastSpell = False
        self.fightReadySent = False
        self._confirmTurnEnd = False
        self._moveRequestFails = 0
        self._lastMoveRequestTime = None
        self._forbidenCells = set()
        self._turnStartPlaying = False

    def pushed(self) -> bool:
        self.init()
        return True

    @property
    def turnsList(self) -> list[float]:
        return self.battleFrame._turnsList

    @property
    def playerStats(self) -> "EntityStats":
        return StatsManager().getStats(self.currentPlayer.id)

    @property
    def spellId(self) -> int:
        return BotConfig().getPrimarySpellId(self.currentPlayer.breedId)

    @property
    def playerManager(self) -> "PlayedCharacterManager":
        return PlayedCharacterManager.getInstance(self.currentPlayer.login)

    @property
    def turnFrame(self) -> "FightTurnFrame":
        return Kernel().worker.getFrameByName("FightTurnFrame")

    @property
    def fightContextFrame(self) -> "FightContextFrame":
        return Kernel().worker.getFrameByName("FightContextFrame")

    @property
    def entitiesFrame(self) -> "FightEntitiesFrame":
        return Kernel().worker.getFrameByName("FightEntitiesFrame")

    @property
    def battleFrame(self) -> "FightBattleFrame":
        return Kernel().worker.getFrameByName("FightBattleFrame")

    @property
    def partyFrame(self) -> "BotPartyFrame":
        return Kernel().worker.getFrameByName("BotPartyFrame")

    @property
    def fightCount(self) -> int:
        return self._fightCount

    def pulled(self) -> bool:
        self._spellw = None
        if self._reachableCells:
            self._reachableCells.clear()
        self._turnAction.clear()
        return True

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

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

    def findCellsWithLosToTargets(self, spellw: SpellWrapper, targets: list[Target], fighterCell: int) -> list[int]:
        LosDetector.clearCache()
        hasLosToTargets = dict[int, list[Target]]()
        spellZone = self.getSpellZone(spellw)
        maxRangeFromFighter = 0
        for target in targets:
            currSpellZone = spellZone.getCells(target.pos.cellId)
            los = LosDetector.getCells(DataMapProvider(), currSpellZone, target.pos.cellId)
            if fighterCell in los:
                return 0, {fighterCell: [target]}
            for cellId in los:
                if cellId not in hasLosToTargets:
                    hasLosToTargets[cellId] = list[Target]()
                hasLosToTargets[cellId].append(target)
                maxRangeFromFighter = max(maxRangeFromFighter, target.distFromPlayer)
        return maxRangeFromFighter, hasLosToTargets

    def findPathToTarget(self, spellw: SpellWrapper, targets: list[Target]) -> Tuple[Target, list[int]]:
        if not targets:
            return None, None
        for target in targets:
            if target.pos.distanceTo(self.fighterPos) <= 1:
                return target, []
        maxRangeFromFighter, hasLosToTargets = self.findCellsWithLosToTargets(spellw, targets, self.fighterPos.cellId)
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
                if nextCellId not in self._forbidenCells and nextCellId not in visited and nextCellId in reachableCells:
                    parentOfCell[nextCellId] = currCellId
                    if nextCellId in hasLosToTargets:
                        path = self.buildPath(parentOfCell, nextCellId)
                        return hasLosToTargets[nextCellId][0], path
                    heuristic = (
                        usedPms
                        + 1
                        + 10
                        * sum([MapTools.getDistance(nextCellId, cellId) for cellId in hasLosToTargets])
                        / len(hasLosToTargets)
                    )
                    if heuristic < BtestAlternativeCost:
                        bestAlternative = nextCellId
                        BtestAlternativeCost = heuristic
                    queue.put((heuristic, usedPms + 1, nextCellId))
        if bestAlternative is not None:
            path = self.buildPath(parentOfCell, bestAlternative)
            return None, path
        return None, None

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
        self.nextTurnAction("Invisible mob blocking way")

    def playTurn(self):
        if not self.turnFrame.myTurn or not self.currentPlayer:
            return
        Logger().info(f"[FightBot] Turn playing - {self.currentPlayer.name}")
        targets = self.getTargetableEntities(self.spellw, targetSum=False)
        if not targets:
            targets = self.getTargetableEntities(self.spellw, targetSum=True)
            if not targets:
                self.addTurnAction(self.turnEnd, [])
                self.nextTurnAction("play turn no targets")
                return
        Logger().info(f"[FightBot] MP : {self.movementPoints}, AP : {self.actionPoints}.")
        Logger().info(f"[FightBot] Current attack spell : {self.spellw.spell.name}.")
        Logger().info(f"[FightBot] Current spell range : {self.getActualSpellRange(self.spellw)}.")
        Logger().info(f"[FightBot] Found targets : {[str(tgt) for tgt in targets]}.")
        target, path = self.findPathToTarget(self.spellw, targets)
        if path is not None:
            reachableCells = FightReachableCellsMaker(self.fighterInfos, self.fighterPos.cellId, int(self.movementPoints)).reachableCells
            correctedPath = []
            targetInRange = True
            for cellId in path:
                if cellId not in reachableCells:
                    targetInRange = False
                    break
                correctedPath.append(cellId)
            self._currentPath = correctedPath
            self._currentTarget = target
            if self._currentPath:
                self.addTurnAction(self.askMove, [self._currentPath])
            if target and targetInRange:
                self.addTurnAction(self.castSpell, [self.spellId, target.pos.cellId])
            if not target:
                self.addTurnAction(self.turnEnd, [])
        else:
            Logger().info("[FightBot] No path found.")
            self.addTurnAction(self.turnEnd, [])
        self.nextTurnAction("play turn")

    def getActualSpellRange(self, spellw: SpellWrapper) -> int:
        range: int = spellw["range"]
        minRange: int = spellw["minRange"]
        if spellw["rangeCanBeBoosted"]:
            range += self.playerStats.getStatTotalValue(StatIds.RANGE) - self.playerStats.getStatAdditionalValue(
                StatIds.RANGE
            )
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
        range = self.getActualSpellRange(spellw)
        minRange = spellw["minRange"]
        if range is None or minRange is None:
            raise Exception(f"Spell range is None, {minRange} {range}")
        spellShape = self.getSpellShape(spellw)
        castInLine = spellw["castInLine"] or (spellShape == SpellShapeEnum.l)
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

    def nextTurnAction(self, event=None) -> None:
        if self._isRequestingMovement or self._requestingCastSpell or not self._myTurn:
            Logger().warning(f"[FightAlgo] Next turn action called by {event} while requestingMovement: {self._isRequestingMovement}, requestingCastSpell: {self._requestingCastSpell}, myTurn: {self._myTurn}")
            return
        if not self.battleFrame:
            Logger().error("[FightAlgo] No battle frame found")
            return
        if self.battleFrame._sequenceFrames or self.battleFrame._executingSequence:
            Logger().info(
                f"[FightAlgo] Waiting for {len(self.battleFrame._sequenceFrames)} sequences to end, "
                    f"currently executing {self.battleFrame._executingSequence} ..."
            )
            self.battleFrame.logState()
            KernelEventsManager().once(KernelEvent.SEQUENCE_EXEC_FINISHED, self.nextTurnAction)
            return
        if self.VERBOSE:
            Logger().info(f"[FightBot] Next turn actions, {[a['fct'].__name__ for a in self._turnAction]}")
        if self._turnAction:
            action = self._turnAction.pop(0)
            self._waitingSeqEnd = True
            action["fct"](*action["args"])
        else:
            self.playTurn()

    def updateReachableCells(self) -> None:
        self._reachableCells = FightReachableCellsMaker(self.fighterInfos).reachableCells

    def canCastSpell(self, spellw: SpellWrapper, targetId: int) -> bool:
        return CurrentPlayedFighterManager().canCastThisSpell(self.spellId, spellw.spellLevel, targetId, [""])

    def process(self, msg: Message) -> bool:
        
        if isinstance(msg, GameFightOptionStateUpdateMessage):
            if msg.option not in BotConfig().fightOptions:
                BotConfig().fightOptions.append(msg.option)
            if Kernel().worker.getFrameByName("RoleplayEntitiesFrame"):
                return False
            return True

        elif isinstance(msg, GameFightJoinMessage):
            Logger().separator("Joined fight", "*")
            BotConfig().lastFightTime = perf_counter()
            self._fightCount += 1
            self._spellCastFails = 0
            self._inFight = True
            self.fightReadySent = False 
            if BotConfig().isLeader:
                if FightOptionsEnum.FIGHT_OPTION_SET_SECRET not in BotConfig().fightOptions:
                    gfotmsg = GameFightOptionToggleMessage()
                    gfotmsg.init(FightOptionsEnum.FIGHT_OPTION_SET_SECRET)
                    ConnectionsHandler().send(gfotmsg)
                if FightOptionsEnum.FIGHT_OPTION_SET_TO_PARTY_ONLY not in BotConfig().fightOptions:
                    gfotmsg = GameFightOptionToggleMessage()
                    gfotmsg.init(FightOptionsEnum.FIGHT_OPTION_SET_TO_PARTY_ONLY)
                    ConnectionsHandler().send(gfotmsg)
            return True

        elif isinstance(msg, GameFightEndMessage):
            self._inFight = False
            return True

        elif isinstance(msg, GameActionFightNoSpellCastMessage):
            Logger().error(f"[FightBot] Failed to cast spell")
            if self._requestingCastSpell:
                self._turnAction.clear()
                self._requestingCastSpell = False
                if self._spellCastFails > 2:
                    self.turnEnd()
                    return True
                self._spellCastFails += 1
                self.playTurn()
            return True

        elif isinstance(msg, GameMapNoMovementMessage):
            Logger().error(f"[FightBot] Failed to move")
            if self._isRequestingMovement and self.turnFrame and self.turnFrame.myTurn:
                self._turnAction.clear()
                self._isRequestingMovement = False
                if self._moveRequestFails > 2:
                    self.turnEnd()
                    return True
                self._moveRequestFails += 1
                self.playTurn()
            return True

        elif isinstance(msg, GameFightShowFighterMessage):
            if BotConfig().isLeader:
                fighterId = msg.informations.contextualId
                self._turnPlayed = 0
                self._myTurn = False
                player = BotConfig().getPlayerById(fighterId)
                if player and player.id != BotConfig().character.id:
                    Logger().info(f"[FightBot] Party member {player.name} joined fight.")
                    startFightMsg = GameFightReadyMessage()
                    startFightMsg.init(True)
                    ConnectionsHandler.getInstance(player.login).send(startFightMsg)
                elif fighterId > 0 and fighterId != BotConfig().character.id:
                    Logger().error(f"[FightBot] Unknown Player {fighterId} joined fight.")
                else:
                    Logger().info(f"[FightBot] Monster {fighterId} appeared.")
                notjoined = [
                    m.name for m in BotConfig().fightPartyMembers if not self.entitiesFrame.getEntityInfos(m.id)
                ]
                if notjoined:
                    Logger().info(f"[FightBot] Waiting for {notjoined} party members to join fight.")
                elif not self.fightReadySent:
                    Logger().info(f"[FightBot] All party members joined fight.")
                    startFightMsg = GameFightReadyMessage()
                    startFightMsg.init(True)
                    ConnectionsHandler().send(startFightMsg)
                    self.fightReadySent = True
                    return True
            return True

        elif isinstance(msg, SequenceEndMessage):
            if self._myTurn:
                if self._seqQueue:
                    self._seqQueue.pop()
                    if not self._seqQueue:
                        self._waitingSeqEnd = False
                        self.checkCanPlay()
            return True

        elif isinstance(msg, SequenceStartMessage):
            if self._myTurn:
                self._waitingSeqEnd = True
                self._seqQueue.append(msg)
            return True

        elif isinstance(msg, GameFightTurnStartMessage):
            Logger().separator(f"Player {msg.id} turn to play", "~")
            self._currentPlayerId = msg.id
            if not self._lastPlayerId:
                self._lastPlayerId = self._currentPlayerId
            if not isinstance(msg, GameFightTurnResumeMessage):
                BuffManager().decrementDuration(msg.id)
                BuffManager().resetTriggerCount(msg.id)
            if self.battleFrame:
                self.battleFrame.removeSavedPosition(msg.id)
                if self.entitiesFrame:
                    for entityId, infos in self.entitiesFrame.entities.items():
                        if infos and infos.stats.summoner == msg.id:
                            self.battleFrame.removeSavedPosition(entityId)
            self.currentPlayer = BotConfig().getPlayerById(self._currentPlayerId)
            if self.currentPlayer:
                self.onPlayer()
            if self._turnStartPlaying:
                self.checkCanPlay()
            return True
        
        elif isinstance(msg, GameFightTurnEndMessage):
            if self._myTurn:
                self._isRequestingMovement = False
                self._requestingCastSpell
                self._lastPlayerId = msg.id
                self._myTurn = False
            return True

        elif isinstance(msg, GameFightTurnStartPlayingMessage):
            if self._myTurn:
                self.checkCanPlay()
            else:
                self._turnStartPlaying = True

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
            if textId == 4897:  # Something is blocking the way
                self._forbidenCells.add(self._currentPath[1])
                self._isRequestingMovement = False
                self._turnAction.clear()
                self.playTurn()
            if textId == 144451:  # An obstacle is blocking LOS
                self._requestingCastSpell = False
                self._turnAction.clear()
                self.turnEnd()
            return True

        elif isinstance(msg, GameFightTurnReadyRequestMessage):
            if self.battleFrame._executingSequence:
                Logger().warn("[FightBot] Delaying turn end acknowledgement because we're still in a sequence.")
                self._confirmTurnEnd = True
            else:
                self.confirmTurnEnd()
                self._turnStartPlaying = False
            return True

        return False

    def onPlayer(self) -> None:
        if not self.playerManager:
            Logger().warning(f"[FightBot] {self.currentPlayer.name} seems to be disconnected")
            PlayedCharacterManager.onceThreadRegister(self.currentPlayer.login, self.onPlayer)
            return
        Logger().info(f"[FightBot] It's {self.currentPlayer.name}'s turn to play")
        self._forbidenCells.clear()
        self._myTurn = True
        self.preparePlayableCharacter()
        self.checkCanPlay()
        self._turnPlayed += 1
        
    @property
    def actionPoints(self) -> int:
        stats = CurrentPlayedFighterManager().getStats()
        return stats.getStatTotalValue(StatIds.ACTION_POINTS)

    @property
    def movementPoints(self) -> int:
        stats = CurrentPlayedFighterManager().getStats()
        return stats.getStatTotalValue(StatIds.MOVEMENT_POINTS)

    def checkCanPlay(self):
        if not self.turnFrame or not self.turnFrame.myTurn:
            return
        if self._confirmTurnEnd:
            self.confirmTurnEnd()
            self._confirmTurnEnd = False
            return True
        if self._myTurn and not self._waitingSeqEnd:
            self.nextTurnAction("checkCanPlay")
                    
    def turnEnd(self) -> None:
        if self.currentPlayer is not None:
            self._spellCastFails = 0
            self._myTurn = False
            self._seqQueue.clear()
            self._turnAction.clear()
            gftfmsg: GameFightTurnFinishMessage = GameFightTurnFinishMessage()
            gftfmsg.init(False)
            ConnectionsHandler.getInstance(self.currentPlayer.login).send(gftfmsg)

    @property
    def fighterInfos(self) -> "GameFightFighterInformations":
        return self.entitiesFrame.getEntityInfos(self.currentPlayer.id)

    @property
    def fighterPos(self) -> "MapPoint":
        return MapPoint.fromCellId(self.fighterInfos.disposition.cellId)

    def getTargetableEntities(self, spellw: SpellWrapper, targetSum=False) -> list[Target]:
        result = list[Target]()
        if not self.entitiesFrame or not self.battleFrame:
            return []
        if self.fighterInfos is None:
            return []
        for entity in self.entitiesFrame.entities.values():
            if entity.contextualId < 0 and isinstance(entity, GameFightMonsterInformations):
                monster = entity
                if (
                    monster.spawnInfo.teamId != self.fighterInfos.spawnInfo.teamId
                    and float(entity.contextualId) not in self.battleFrame._deadTurnsList
                    and entity.contextualId not in self.fightContextFrame.hiddenEntites
                    and (targetSum or not monster.stats.summoned)
                    and self.canCastSpell(spellw, entity.contextualId)
                    and entity.disposition.cellId != -1
                ):
                    result.append(Target(entity, self.fighterInfos.disposition.cellId))
        return result

    def castSpell(self, spellId: int, cellId: bool) -> None:
        if not self._requestingCastSpell:
            if self.canCastSpell(self.spellw, cellId):
                self._requestingCastSpell = True
                BotEventsManager().onceFighterCastedSpell(self._currentPlayerId, cellId, self.onSpellCasted)
                gafcrmsg = GameActionFightCastRequestMessage()
                gafcrmsg.init(spellId, cellId)
                ConnectionsHandler.getInstance(self.currentPlayer.login).send(gafcrmsg)

    def onSpellCasted(self) -> None:
        if self._requestingCastSpell:
            Logger().info(f"[FightBot] Spell casted.")
            self._requestingCastSpell = False
            self.checkCanPlay()

    def askMove(self, cells: list[int] = []) -> bool:
        if not self._lastMoveRequestTime:
            self._lastMoveRequestTime = perf_counter()
        elif perf_counter() - self._lastMoveRequestTime  < self.CONSECUTIVE_MOVEMENT_DELAY:
            Logger().warning(f"[FightBot] too soon to request movement again.")
            Kernel().worker.terminated.wait(self.CONSECUTIVE_MOVEMENT_DELAY - (perf_counter() - self._lastMoveRequestTime))
        self._isRequestingMovement = True
        path: MovementPath = MovementPath()
        path.fillFromCellIds(cells[0:-1])
        path.end = MapPoint.fromCellId(cells[-1])
        path.path[-1].orientation = path.path[-1].step.orientationTo(path.end)
        Logger().info(f"[FightBot] Moving {path}.")
        gmmrmsg = GameMapMovementRequestMessage()
        keyMovements = path.keyMoves()
        currMapId = PlayedCharacterManager().currentMap.mapId
        gmmrmsg.init(keyMovements, currMapId)
        BotEventsManager().onceFighterMoved(self._currentPlayerId, self.onMovementApplied)
        ConnectionsHandler.getInstance(self.currentPlayer.login).send(gmmrmsg)
        self._lastMoveRequestTime = perf_counter()
        return True

    def onMovementApplied(self) -> None:
        if self._isRequestingMovement:
            Logger().info(f"[FightBot] Movement applied.")
            self._isRequestingMovement = False
            self.checkCanPlay()

    def confirmTurnEnd(self) -> None:
        if self.currentPlayer:
            fighterInfos = self.entitiesFrame.getEntityInfos(self.currentPlayer.id)
            if fighterInfos:
                BuffManager().markFinishingBuffs(self.currentPlayer.id)
                SpellWrapper.refreshAllPlayerSpellHolder(self.currentPlayer.id)
            else:
                Logger().error(f"[FightBot] Can't find fighter infos for player {self.currentPlayer.id}")
            spellCastManager = CurrentPlayedFighterManager().getSpellCastManagerById(self.currentPlayer.id)
            if spellCastManager:
                spellCastManager.nextTurn()
        self.currentPlayer = None
        turnEnd = GameFightTurnReadyMessage()
        turnEnd.init(True)
        ConnectionsHandler().send(turnEnd)

    def preparePlayableCharacter(self) -> None:            
        self._spellCastFails = False
        self._requestingCastSpell = False
        self._isRequestingMovement = False
        CurrentPlayedFighterManager().playerManager = PlayedCharacterManager.getInstance(self.currentPlayer.login)
        CurrentPlayedFighterManager().currentFighterId = self._currentPlayerId
        CurrentPlayedFighterManager.conn = ConnectionsHandler.getInstance(self.currentPlayer.login)
        CurrentPlayedFighterManager().resetPlayerSpellList()
        SpellWrapper.refreshAllPlayerSpellHolder(self._currentPlayerId)
        SpellInventoryManagementFrame().applySpellGlobalCoolDownInfo(self._currentPlayerId)
        self.spellw = self.playerManager.getSpellById(self.spellId)
        self._spellCastFails = 0
        self._moveRequestFails = 0
        self._seqQueue.clear()
        self._turnAction.clear()
        if self.turnFrame:
            self.turnFrame.myTurn = True