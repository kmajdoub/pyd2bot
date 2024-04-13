import random
import threading
from queue import PriorityQueue
from time import perf_counter
from types import FunctionType
from typing import TYPE_CHECKING, Tuple

from prettytable import PrettyTable

from pyd2bot.logic.fight.messages.MuleSwitchedToCombatContext import \
    MuleSwitchedToCombatContext
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.misc.BotEventsmanager import BotEventsManager
from pyd2bot.models.session.models import Character
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import \
    HaapiEventsManager
from pydofus2.com.ankamagames.atouin.managers.EntitiesManager import \
    EntitiesManager
from pydofus2.com.ankamagames.atouin.utils.DataMapProvider import \
    DataMapProvider
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.datacenter.effects.EffectInstance import \
    EffectInstance
from pydofus2.com.ankamagames.dofus.datacenter.monsters.Monster import Monster
from pydofus2.com.ankamagames.dofus.datacenter.spells.Spell import Spell
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
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.BuffManager import \
    BuffManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.CurrentPlayedFighterManager import \
    CurrentPlayedFighterManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.FightersStateManager import \
    FightersStateManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.miscs.FightReachableCellsMaker import \
    FightReachableCellsMaker
from pydofus2.com.ankamagames.dofus.logic.game.fight.miscs.TackleUtil import \
    TackleUtil
from pydofus2.com.ankamagames.dofus.network.enums.FightOptionsEnum import \
    FightOptionsEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightCastRequestMessage import \
    GameActionFightCastRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightNoSpellCastMessage import \
    GameActionFightNoSpellCastMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.sequence.SequenceEndMessage import \
    SequenceEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.sequence.SequenceStartMessage import \
    SequenceStartMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightEndMessage import \
    GameFightEndMessage
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
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.jerakine.types.positions.MovementPath import \
    MovementPath
from pydofus2.com.ankamagames.jerakine.types.zones.Cross import Cross
from pydofus2.com.ankamagames.jerakine.types.zones.DisplayZone import DisplayZone
from pydofus2.com.ankamagames.jerakine.types.zones.Lozenge import Lozenge
from pydofus2.com.ankamagames.jerakine.utils.display.spellZone.SpellShapeEnum import \
    SpellShapeEnum
from pydofus2.damageCalculation.tools.StatIds import StatIds
from pydofus2.mapTools import MapTools

lock = threading.Lock()
if TYPE_CHECKING:
    pass


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
        self._suspectedUnreachableCell = None
        self.fightResumed = False
        self._challengeChosen = False

    def onFightJoined(self, event, isFightStarted, fightType, isTeamPhase, timeMaxBeforeFightStart):
        BotConfig().lastFightTime = perf_counter()
        self._fightCount += 1
        self._spellCastFails = 0
        self._inFight = True
        self.fightReadySent = False
        if not BotConfig().fightOptionsSent:
            if BotConfig().isLeader:
                gfotmsg = GameFightOptionToggleMessage()
                gfotmsg.init(FightOptionsEnum.FIGHT_OPTION_SET_SECRET)
                ConnectionsHandler().send(gfotmsg)
                if not BotConfig().followers:
                    gfotmsg = GameFightOptionToggleMessage()
                    gfotmsg.init(FightOptionsEnum.FIGHT_OPTION_SET_CLOSED)
                    ConnectionsHandler().send(gfotmsg)
            BotConfig().fightOptionsSent = True

    def onChallengeBonusChosen(self, event, bonusId):
        self._challengeChosen = True
        if BotConfig().isLeader:
            Logger().info(f"Challenge bonus {bonusId} chosen.")
            if self.allMembersJoinedFight():
                self.sendFightReady()
            else:
                Logger().info("Waiting for members to join fight.")

    def onFighterShowed(self, event, fighterId):
        if BotConfig().isLeader:
            self._turnPlayed = 0
            self._myTurn = False
            player = BotConfig().getPlayerById(fighterId)
            if player:
                if player.id != BotConfig().character.id:
                    self.onMemberJoinedFight(player)
                else:
                    Logger().info(f"Party Leader {player.name} joined fight.")
            elif fighterId > 0 and fighterId != BotConfig().character.id:
                Logger().error(f"Unknown Player {fighterId} joined fight.")
            elif fighterId < 0:
                Logger().info(f"Monster {fighterId} appeared.")

    def onFightResumed(self, event):
        self.fightResumed = True

    def pushed(self) -> bool:
        Logger().warning(f"{self.__class__} has been pushed")
        self.init()
        KernelEventsManager().on(KernelEvent.ServerTextInfo, self.onServerTextInfo, originator=self)
        KernelEventsManager().once(KernelEvent.FightResumed, self.onFightResumed, originator=self)
        KernelEventsManager().on(KernelEvent.FighterShowed, self.onFighterShowed, originator=self)
        KernelEventsManager().once(KernelEvent.FightJoined, self.onFightJoined, originator=self)
        KernelEventsManager().on(
            KernelEvent.ChallengeBonusSelected,
            self.onChallengeBonusChosen,
            timeout=5,
            ontimeout=lambda _: self.onChallengeBonusChosen(None, "N/A"),
            originator=self,
        )
        KernelEventsManager().once(KernelEvent.FightEnded, self.onFightEnded, originator=self)
        KernelEventsManager().on(KernelEvent.FightOptionStateUpdate, self.onFightOptionStateUpdate, originator=self)
        KernelEventsManager().on(KernelEvent.ActionFightNoSpellCast, self.onActionFightNoSpellCast, originator=self)
        KernelEventsManager().on(KernelEvent.FightMapNoMovement, self.onFightMapNoMovement, originator=self)
        KernelEventsManager().on(KernelEvent.SequenceEnd, self.onSequenceEnd, originator=self)
        KernelEventsManager().on(KernelEvent.SequenceStart, self.onSequenceStart, originator=self)
        KernelEventsManager().on(KernelEvent.FightTurnStart, self.onFightTurnStart, originator=self)
        KernelEventsManager().on(KernelEvent.FightTurnEnd, self.onFightTurnEnd, originator=self)
        KernelEventsManager().on(KernelEvent.FightTurnStartPlaying, self.onFightTurnStartPlaying, originator=self)
        KernelEventsManager().on(KernelEvent.FightTurnReadyRequest, self.onFightTurnReadyRequest, originator=self)
        BotEventsManager().on(BotEventsManager().MULE_FIGHT_CONTEXT, self.onMuleSwitchedToCombatContext, originator=self)
        return True

    @property
    def playerStats(self) -> "EntityStats":
        return StatsManager().getStats(self.currentPlayer.id)

    @property
    def spellId(self) -> int:
        return BotConfig().getPrimarySpellId(self.currentPlayer.breedId)

    @property
    def secondarySpellId(self) -> int:
        return BotConfig().getSecondarySpellId(self.currentPlayer.breedId)

    @property
    def playerManager(self) -> "PlayedCharacterManager":
        if not self.currentPlayer:
            Logger().warning("Asking for player manager for None current player")
            return None
        return PlayedCharacterManager.getInstance(self.currentPlayer.login)

    @property
    def fightCount(self) -> int:
        return self._fightCount

    @property
    def connection(self) -> "ConnectionsHandler":
        return ConnectionsHandler.getInstance(self.currentPlayer.login)

    @property
    def hitpoints(self) -> int:
        stats = CurrentPlayedFighterManager().getStats()
        return stats.getHealthPoints()

    @property
    def actionPoints(self) -> int:
        stats = CurrentPlayedFighterManager().getStats()
        return stats.getStatTotalValue(StatIds.ACTION_POINTS)

    @property
    def movementPoints(self) -> int:
        stats = CurrentPlayedFighterManager().getStats()
        return stats.getStatTotalValue(StatIds.MOVEMENT_POINTS)

    @property
    def fighterInfos(self) -> "GameFightFighterInformations":
        return Kernel().fightEntitiesFrame.getEntityInfos(self.currentPlayer.id)

    @property
    def fighterPos(self) -> "MapPoint":
        if EntitiesManager().getEntity(self.currentPlayer.id) is None:
            return None
        return EntitiesManager().getEntity(self.currentPlayer.id).position
    
    def pulled(self) -> bool:
        Logger().warning(f"{self.__class__} has been pulled")
        self._spellw = None
        if self._reachableCells:
            self._reachableCells.clear()
        self._turnAction.clear()
        KernelEventsManager().clearAllByOrigin(self)
        BotEventsManager().clearAllByOrigin(self)
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
        hasLosToTargets = dict[int, list[Target]]()
        perf_counter()
        spellZone = self.getSpellZone(spellw)
        maxRangeFromFighter = 0
        for target in targets:
            currSpellZone = spellZone.getCells(target.pos.cellId)
            for cell in currSpellZone:
                p = MapPoint.fromCellId(cell)
                line = MapTools.getMpLine(target.pos.cellId, p.cellId)
                los = True
                if len(line) > 1:
                    for mp in line[:-1]:
                        if not DataMapProvider().pointLos(mp.x, mp.y, False):
                            los = False
                            break
                if los:
                    if fighterCell == p.cellId:
                        return 0, {fighterCell: [target]}
                    if p.cellId not in hasLosToTargets:
                        hasLosToTargets[p.cellId] = list[Target]()
                    hasLosToTargets[p.cellId].append(target)
                    maxRangeFromFighter = max(maxRangeFromFighter, target.distFromPlayer)
        # Logger().info(f"findCellsWithLosToTargets took {perf_counter() - s} seconds")
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
                if (
                    nextCellId not in self._forbidenCells
                    and nextCellId not in visited
                    and nextCellId in reachableCells
                ):
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

    def onInvisibleMobBlockingWay(self):
        self._turnAction.clear()
        self.addTurnAction(self.turnEnd, [])
        self.nextTurnAction("Invisible mob blocking way")

    def getTargetableEntities(self, spellw: SpellWrapper, targetSum=False, boneId=None) -> list[Target]:
        result = list[Target]()
        infosTable = list[dict]()
        if not Kernel().fightEntitiesFrame or not Kernel().battleFrame:
            Logger().error("EntitiesFrame or BattleFrame is not found")
            return []
        if self.fighterInfos is None:
            Logger().warning(
                f"Fighter {self.currentPlayer} not found in entities frame : {Kernel().fightEntitiesFrame.entities}"
            )
            return []
        for entity in Kernel().fightEntitiesFrame.entities.values():
            if entity.contextualId < 0:
                monster = entity
                canCast, reason = self.canCastSpell(entity.contextualId)
                stats = StatsManager().getStats(entity.contextualId)
                hp = stats.getHealthPoints()
                stats.getMaxHealthPoints()
                ismonster = isinstance(entity, GameFightMonsterInformations)
                name = "unknown"
                level = "unknown"
                if isinstance(entity, GameFightMonsterInformations):
                    monster = Monster.getMonsterById(entity.creatureGenericId)
                    name = monster.name
                    level = entity.creatureLevel
                status = FightersStateManager().getStatus(self.fighterInfos.contextualId)
                entry = {
                    "name": name,
                    "level": level,
                    "teamId": entity.spawnInfo.teamId,
                    "dead": entity.contextualId in Kernel().battleFrame.deadFightersList,
                    "hidden": entity.contextualId in Kernel().fightContextFrame.hiddenEntites,
                    "summoned": entity.stats.summoned,
                    "canhit": canCast,
                    "cell": entity.disposition.cellId,
                    "id": entity.contextualId,
                    "reason": reason,
                    "hitpoints": hp,
                    "isMonster": ismonster,
                    "state": status.getActiveStatuses(),
                    "boneId": entity.look.bonesId,
                }
                infosTable.append(entry)
                if (
                    entry["teamId"] != self.fighterInfos.spawnInfo.teamId
                    and not entry["dead"]
                    and not entry["hidden"]
                    and (targetSum or not entry["summoned"])
                    and entry["canhit"]
                    and entry["cell"] != -1
                    and (boneId is None or entity.look.bonesId == boneId)
                ):
                    result.append(Target(entity, self.fighterInfos.disposition.cellId))
        summaryTable = PrettyTable(
            ["name", "id", "boneId", "level", "hitpoints", "hidden", "summoned", "state", "canhit", "reason"]
        )
        for e in infosTable:
            summaryTable.add_row([e[k] for k in summaryTable.field_names])
        Logger().info("\n" + str(summaryTable))
        return result

    def remainsEnemies(self):
        if not self.fighterInfos:
            return None
        for entity in Kernel().fightEntitiesFrame.entities.values():
            if entity.spawnInfo.teamId != self.fighterInfos.spawnInfo.teamId:
                return True

    def playTurn(self):
        if not self.currentPlayer:
            Logger().warning(f"/!\ Play turn called without a defined currentPlayer")
        if not self.remainsEnemies():
            return
        self._currentPath = None
        self._currentTarget = None
        Logger().info(f"Turn playing : {self.currentPlayer.name} ({self.currentPlayer.id}).")
        canCast, reason = self.canCastSpell()
        if not canCast:
            Logger().info(f"Unable to cast spells for reason : {reason}")
            self.addTurnAction(self.turnEnd, [])
            self.nextTurnAction("Play turn no targets")
            return
        if BotConfig().isTreasureHuntSession:
            targetsFiters = [(self.spellw, True, 2672), (self.spellw, True, 91)]
        else:
            targetsFiters = [(self.spellw, False, None), (self.spellw, True, None)]
        for args in targetsFiters:
            targets = self.getTargetableEntities(*args)
            if not targets:
                continue
            Logger().info(f"MP: {self.movementPoints}, AP: {self.actionPoints}, HP: {self.hitpoints}.")
            Logger().info(
                f"Current attack spell : {self.spellw.spell.name}, range: {self.spellw.maxRange}."
            )
            Logger().info(f"Found targets : {[str(tgt) for tgt in targets]}.")
            target, path = self.findPathToTarget(self.spellw, targets)
            if path is not None:
                Logger().info(f"Found path {path} to target {target}.")
                self._currentTarget = target
                mpCount = 0
                mpLost = 0
                apLost = 0
                movementPoints = self.movementPoints
                actionPoints = self.actionPoints
                canHitTarget = target is not None
                if len(path) > 1:
                    lastCellId = path[0]
                    for cellId in path[1:]:
                        tackle = TackleUtil.getTackle(self.fighterInfos, MapPoint.fromCellId(lastCellId))
                        mpLost += int((self.movementPoints - mpCount) * (1 - tackle) + 0.5)
                        apLost += int(actionPoints * (1 - tackle) + 0.5)
                        if apLost < 0:
                            apLost = 0
                        if mpLost < 0:
                            mpLost = 0
                        movementPoints = self.movementPoints - mpLost
                        actionPoints = self.actionPoints - apLost
                        if mpCount < movementPoints:
                            mpCount += 1
                        else:
                            break
                        lastCellId = cellId
                    canHitTarget = target and actionPoints >= self.spellw["apCost"] and mpCount >= len(path) - 1
                    self._currentPath = path[: mpCount + 1]
                    if len(self._currentPath) > 1:
                        self.addTurnAction(self.askMove, [self._currentPath])
                if canHitTarget:
                    self.addTurnAction(self.castSpell, [self.spellId, target.pos.cellId])
                else:
                    self.addTurnAction(self.turnEnd, [])
                break
        else:
            if not self.remainsEnemies():
                return
            if BotConfig().isTreasureHuntSession:
                raise Exception("No path to target found")
            else:
                self.addTurnAction(self.turnEnd, [])
        self.nextTurnAction("play turn")

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

    def getSpellZone(self, spellw: SpellWrapper) -> DisplayZone:
        range = spellw["range"]
        minRange = spellw["minRange"]
        if range is None or minRange is None:
            raise Exception(f"Spell range is None, {minRange} {range}")
        if range < minRange:
            range = minRange;
        spellShape = self.getSpellShape(spellw)
        castInLine = spellw["castInLine"] or (spellShape == SpellShapeEnum.l)
        if castInLine:
            if spellw["castInDiagonal"]:
                return Cross(SpellShapeEnum.UNKNOWN, minRange, range, DataMapProvider(), False, True)
            return Cross(SpellShapeEnum.UNKNOWN, minRange, range, DataMapProvider(), True)
        elif spellw["castInDiagonal"]:
            return Cross(SpellShapeEnum.UNKNOWN, minRange, range, DataMapProvider(), True)
        else:
            return Lozenge(SpellShapeEnum.UNKNOWN, minRange, range, DataMapProvider())

    def addTurnAction(self, fct: FunctionType, args: list) -> None:
        self._turnAction.append({"fct": fct, "args": args})

    def nextTurnAction(self, event=None) -> None:
        if self._isRequestingMovement or self._requestingCastSpell or not self._myTurn:
            return
        if not Kernel().battleFrame:
            Logger().error("[FightAlgo] No battle frame found")
            return
        if Kernel().battleFrame._sequenceFrames or Kernel().battleFrame._executingSequence:
            Logger().warning(
                f"Waiting for {len(Kernel().battleFrame._sequenceFrames)} sequences to end, "
                f"currently executing {Kernel().battleFrame._executingSequence} ..."
            )
            Kernel().battleFrame.logState()
            KernelEventsManager().once(KernelEvent.SequenceExecFinished, self.nextTurnAction, originator=self)
            return
        if self.VERBOSE:
            Logger().info(f"Next turn actions, {[a['fct'].__name__ for a in self._turnAction]}")
        if self._turnAction:
            action = self._turnAction.pop(0)
            action["fct"](*action["args"])
        else:
            self.playTurn()

    def updateReachableCells(self) -> None:
        self._reachableCells = FightReachableCellsMaker(self.fighterInfos).reachableCells

    def canCastSpell(self, targetId: int = 0) -> bool:
        return CurrentPlayedFighterManager().canCastThisSpell(self.spellId, self.spellw.spellLevel, targetId)

    def allMembersJoinedFight(self) -> bool:
        for member in BotConfig().fightPartyMembers:
            if not Kernel().fightEntitiesFrame.getEntityInfos(member.id):
                return False
        return True

    def onMemberJoinedFight(self, player: Character):
        Logger().info(f"Follower '{player.name}' joined fight.")
        if self.fightResumed:
            return Logger().warning("Fight resumed so wont check if members joined or not.")
        if self.fightReadySent:
            return Logger().warning("Fight ready already sent so we wont check if members joined or not.")
        playerManager = PlayedCharacterManager.getInstance(player.login)
        if not playerManager:
            return Logger().warning(f"Player manager not found for {player.name}, probably diconnected")
        playerManager.isFighting = True
        self.sendFightReady(ConnectionsHandler.getInstance(player.login))
        if self.allMembersJoinedFight():
            Logger().info(f"All party members joined fight.")
            if self._challengeChosen:
                self.sendFightReady()
            self.fightReadySent = True
        else:
            missing = [
                m.name for m in BotConfig().fightPartyMembers if not Kernel().fightEntitiesFrame.getEntityInfos(m.id)
            ]
            Logger().info(f"Members missing : {missing}")

    def sendFightReady(self, connh=None):
        if not connh:
            connh = ConnectionsHandler()
        startFightMsg = GameFightReadyMessage()
        startFightMsg.init(True)
        connh.send(startFightMsg)

    def onFightEnded(self, event):
        self._inFight = False
        if BotConfig().followers:
            for player in BotConfig().followers:
                playerManager = PlayedCharacterManager.getInstance(player.login)
                if playerManager:
                    playerManager.isFighting = False
        Kernel().worker.removeFrame(self)

    def onFightOptionStateUpdate(self, event, fightId, teamId, option, state):
        if option not in BotConfig().fightOptions:
            BotConfig().fightOptions.append(option)

    def onActionFightNoSpellCast(self, event):
            if not self.currentPlayer:
                return
            Logger().error(f"Failed to cast spell")
            if self._requestingCastSpell:
                self._turnAction.clear()
                self._requestingCastSpell = False
                if self._spellCastFails > 2:
                    self.turnEnd()
                    return True
                self._spellCastFails += 1
                self.playTurn()

    def onFightMapNoMovement(self, event):
        if not self.currentPlayer:
            return
        Logger().error(f"Failed to move")
        if self._isRequestingMovement and Kernel().turnFrame and Kernel().turnFrame.myTurn:
            self._turnAction.clear()
            self._isRequestingMovement = False
            if self._moveRequestFails > 2:
                self.turnEnd()
                return True
            self._moveRequestFails += 1
            self.playTurn()

    def onSequenceEnd(self, event):
        if self._myTurn:
            if self._seqQueue:
                self._seqQueue.pop()
                if not self._seqQueue:
                    self._waitingSeqEnd = False
                    self.checkCanPlay()

    def onSequenceStart(self, event, sequenceType, authorId):
        if self._myTurn:
            self._waitingSeqEnd = True
            self._seqQueue.append(SequenceStartMessage().init(sequenceType, authorId))
        return True
    
    def onFightTurnStart(self, event, id):
        self._currentPlayerId = id
        self.currentPlayer = BotConfig().getPlayerById(self._currentPlayerId)
        if self.currentPlayer:
            self.onPlayer()
        if self._turnStartPlaying:
            self.checkCanPlay()
        
    def onFightTurnEnd(self, event, id):
        if self._myTurn:
            self._isRequestingMovement = False
            self._requestingCastSpell
            self._lastPlayerId = id
            self._myTurn = False

    def onFightTurnStartPlaying(self, event):
        if self._myTurn:
            self.checkCanPlay()
        else:
            self._turnStartPlaying = True

    def onFightTurnReadyRequest(self, event):
        if not Kernel().battleFrame._executingSequence:
            self._turnStartPlaying = False
        else:
            self.currentPlayer = None

    def onMuleSwitchedToCombatContext(self, event, id):
        Logger().info(f"Mule {id} in fight context")
        BotEventsManager().send(BotEventsManager.MULE_FIGHT_CONTEXT, id)

    def process(self, msg: Message) -> bool:
        return False

    def onServerTextInfo(self, event, msgId, msgType, textId, text, params):
        if textId == 4993:  # Wants to use more than the pms available
            self.turnEnd()
        if textId == 4897:  # Something is blocking the way
            pass
        if textId == 144451:  # An obstacle is blocking LOS
            self._requestingCastSpell = False
            self._turnAction.clear()
            self.turnEnd()
        return True

    @property
    def spellw(self) -> SpellWrapper:
        if not self.playerManager:
            Logger().error("Asking for spellw when there is no player manager")
            return None
        res = self.playerManager.getSpellById(self.spellId)
        if not res:
            Logger().error(
                f"Player {self.currentPlayer.name} doesn't have spelllist {self.playerManager.playerSpellList}"
            )
            res = SpellWrapper.create(self.spellId)
            spell = Spell.getSpellById(self.spellId)
            currentCharacterLevel = self.playerManager.limitedLevel
            spellLevels = spell.spellLevelsInfo
            index = 0
            for i in range(len(spellLevels) - 1, -1, -1):
                if currentCharacterLevel >= spellLevels[i].minPlayerLevel:
                    index = i
                    break
            res._spellLevel = spellLevels[index]
            res.spellLevel = index + 1
            self.playerManager.playerSpellList.append(res)
        return res

    def onPlayer(self) -> None:
        if not self.currentPlayer:
            Logger().error(f"Something weird happend, called onPlayer when currrentPlayer is None")
            return
        if not self.playerManager:
            Logger().warning(f"{self.currentPlayer.name} seems to be disconnected")
            BotEventsManager().onceMuleJoinedFightContext(
                self.currentPlayer.id, lambda: self.onPlayer(), originator=self
            )
            return
        Logger().info(f"It's {self.currentPlayer.name}'s turn to play")
        self._forbidenCells.clear()
        self._myTurn = True
        self.preparePlayableCharacter()
        self.checkCanPlay()
        self._turnPlayed += 1
    
    def checkCanPlay(self, event=None):
        if not Kernel().turnFrame or not Kernel().turnFrame.myTurn or not self.currentPlayer or not self.playerManager:
            return
        if Kernel().battleFrame._executingSequence:
            Logger().warning("Delaying checkCanPlay because we're still in a sequence.")
            KernelEventsManager().once(KernelEvent.SequenceExecFinished, self.checkCanPlay, originator=self)
            return False
        
        self.nextTurnAction("checkCanPlay")

    def turnEnd(self) -> None:
        if self.currentPlayer is not None and self.connection is not None:
            self._spellCastFails = 0
            self._myTurn = False
            self._seqQueue.clear()
            self._turnAction.clear()
            gftfmsg = GameFightTurnFinishMessage()
            gftfmsg.init(False)
            if self.connection and self.connection.inGameServer():
                self.connection.send(gftfmsg)
            else:
                Logger().warning("Dropped turn end message coz player seems to be out of server game")

    def castSpell(self, spellId: int, cellId: bool) -> None:
        Logger().info(f"Casting spell {spellId} on cell {cellId}")
        if not self.fighterPos:
            return
        if not self._requestingCastSpell:
            canCast, reason = self.canCastSpell(cellId)
            if canCast:
                line = MapTools.getMpLine(self.fighterPos.cellId, cellId)
                los = True
                if len(line) > 1:
                    for mp in line[:-1]:
                        if not DataMapProvider().pointLos(mp.x, mp.y, False):
                            los = False
                            break
                if not los:
                    Logger().warn(f"Can't cast spell {spellId} on cell {cellId} because of LOS")
                    self._turnAction.clear()
                    self._forbidenCells.add(cellId)
                    return self.nextTurnAction("From cast spell no LOS")
                self._requestingCastSpell = True
                BotEventsManager().onceFighterCastedSpell(
                    self._currentPlayerId, cellId, self.onSpellCasted, originator=self
                )
                gafcrmsg = GameActionFightCastRequestMessage()
                gafcrmsg.init(spellId, cellId)
                self.connection.send(gafcrmsg)
                if random.random() < 0.98:
                    HaapiEventsManager().registerShortcutUse('useSpellLine1')
            else:
                Logger().warning(f"Cant cast spell for reason : {reason}")

    def onSpellCasted(self) -> None:
        if self._requestingCastSpell:
            Logger().info(f"Spell casted.")
            self._requestingCastSpell = False
            self.checkCanPlay()
        else:
            Logger().error(f"Spell casted but player didnt request a cast spell")

    def askMove(self, cells: list[int] = []) -> bool:
        self._isRequestingMovement = True
        path = MovementPath()
        path.fillFromCellIds(cells[:-1])
        path.end = MapPoint.fromCellId(cells[-1])
        path.path[-1].orientation = path.path[-1].step.orientationTo(path.end)
        Logger().info(f"Moving {path}.")
        gmmrmsg = GameMapMovementRequestMessage()
        keyMovements = path.keyMoves()
        currMapId = PlayedCharacterManager().currentMap.mapId
        gmmrmsg.init(keyMovements, currMapId)

        def onMovementApplied(movePath: MovementPath, path: MovementPath) -> None:
            if self._isRequestingMovement:
                Logger().info(f"Movement applied, landed on cell {self.fighterPos.cellId}.")
                self._isRequestingMovement = False
                if movePath.end.cellId != path.end.cellId:
                    Logger().warn(f"Movement failed to reach dest cell : movPath: {movePath} path: {path}")
                    stoppedOnCellIdx = cells.index(movePath.end.cellId)
                    if not stoppedOnCellIdx:
                        Logger().error(f"Couldnt find last reached cell in path.")
                    else:
                        unreachableCell = cells[stoppedOnCellIdx + 1]
                        Logger().warning(f"Cell {unreachableCell} is maybe unreachable")
                        entities_on_cell = Kernel().fightEntitiesFrame.hasEntity(unreachableCell)
                        if entities_on_cell:
                            Logger().warning(f"Entites {[e.id for e in entities_on_cell]} are on cell {unreachableCell}")
                            self._forbidenCells.add(unreachableCell)
                        elif unreachableCell in DataMapProvider().obstaclesCells:
                            Logger().warning(f"Cell {unreachableCell} is an obstacle")
                            self._forbidenCells.add(unreachableCell)
                        self._turnAction.clear()
                self.checkCanPlay()

        BotEventsManager().onceFighterMoved(self._currentPlayerId, onMovementApplied, args=[path.clone()], originator=self)
        self.connection.send(gmmrmsg)
        self._lastMoveRequestTime = perf_counter()
        return True

    def preparePlayableCharacter(self) -> None:
        self._spellCastFails = False
        self._requestingCastSpell = False
        self._isRequestingMovement = False
        CurrentPlayedFighterManager().playerManager = PlayedCharacterManager.getInstance(self.currentPlayer.login)
        CurrentPlayedFighterManager().currentFighterId = self._currentPlayerId
        CurrentPlayedFighterManager().conn = self.connection
        CurrentPlayedFighterManager().resetPlayerSpellList()
        SpellWrapper.refreshAllPlayerSpellHolder(self._currentPlayerId)
        SpellInventoryManagementFrame().applySpellGlobalCoolDownInfo(self._currentPlayerId)
        CurrentPlayedFighterManager().playerManager.isFighting = True
        self._spellCastFails = 0
        self._moveRequestFails = 0
        self._seqQueue.clear()
        self._turnAction.clear()
        if Kernel().turnFrame:
            Kernel().turnFrame.myTurn = True
