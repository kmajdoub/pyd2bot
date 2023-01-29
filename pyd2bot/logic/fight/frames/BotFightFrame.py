import collections
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from time import perf_counter
from types import FunctionType
from typing import TYPE_CHECKING, Tuple
from pydofus2.com.ankamagames.atouin.AtouinConstants import AtouinConstants
from pydofus2.com.ankamagames.atouin.messages.MapLoadedMessage import MapLoadedMessage
from pydofus2.com.ankamagames.atouin.utils.DataMapProvider import DataMapProvider
from pydofus2.com.ankamagames.dofus.datacenter.effects.EffectInstance import EffectInstance
from pydofus2.com.ankamagames.dofus.internalDatacenter.spells.SpellWrapper import SpellWrapper
from pydofus2.com.ankamagames.dofus.internalDatacenter.stats.EntityStats import EntityStats
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightEntitiesFrame import FightEntitiesFrame
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.CurrentPlayedFighterManager import CurrentPlayedFighterManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.miscs.FightReachableCellsMaker import FightReachableCellsMaker
from pydofus2.com.ankamagames.dofus.network.enums.FightOptionsEnum import FightOptionsEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightCastRequestMessage import (
    GameActionFightCastRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightNoSpellCastMessage import (
    GameActionFightNoSpellCastMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.sequence.SequenceEndMessage import SequenceEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.sequence.SequenceStartMessage import SequenceStartMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.character.GameFightShowFighterMessage import (
    GameFightShowFighterMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightEndMessage import GameFightEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightJoinMessage import GameFightJoinMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightOptionToggleMessage import (
    GameFightOptionToggleMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightReadyMessage import GameFightReadyMessage
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
from pydofus2.com.ankamagames.dofus.network.types.game.context.GameContextActorInformations import GameContextActorInformations
from pydofus2.com.ankamagames.jerakine.entities.interfaces.IInteractive import IInteractive
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
from pyd2bot.logic.fight.frames.BotFightTurnFrame import BotFightTurnFrame
from pyd2bot.logic.managers.BotConfig import BotConfig

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightBattleFrame import FightBattleFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightContextFrame import FightContextFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightSpellCastFrame import FightSpellCastFrame
    from pydofus2.com.ankamagames.dofus.logic.game.fight.frames.FightTurnFrame import FightTurnFrame
    from pyd2bot.logic.roleplay.frames.BotPartyFrame import BotPartyFrame





class _Target:
    def __init__(self, entityId: float, pos: MapPoint) -> None:
        self.pos: MapPoint = pos
        self.entityId = entityId

    def __str__(self) -> str:
        return f"({self.entityId} at {self.pos.cellId})"


class BotFightFrame(Frame):
    VERBOSE = True
    ACTION_TIMEOUT = 7
    
    _frameFightListRequest: bool

    _fightCount: int = 0

    _mapPos: list

    _enabled: bool

    _inFight: bool

    _lastEntityOver: IInteractive

    _wait: bool

    _turnPlayed: int

    _myTurn: bool

    _turnAction: list[FunctionType]

    spellId = None

    _lastTarget: int = None

    _spellw: SpellWrapper = None
    
    _fightOptionsSent = False

    def __init__(self):
        self._turnAction = []
        self._spellw = None
        self._botTurnFrame = BotFightTurnFrame()
        self.spellId = BotConfig().primarySpellId
        self._spellCastFails = 0
        self._inFight = False
        super().__init__()

    def pushed(self) -> bool:
        self._enabled = True
        self._myTurn = False
        self._wantcastSpell = None
        self._reachableCells = None
        self._turnAction = []
        self._seqQueue = []
        self._waitingSeqEnd = False
        self._turnPlayed = 0
        self._spellw = None
        self._repeatActionTimeout = None
        self._spellCastFails = 0
        self._fightOptionsSent = False
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
    def spellFrame(self) -> "FightSpellCastFrame":
        return Kernel().worker.getFrame("FightSpellCastFrame")

    @property
    def battleFrame(self) -> "FightBattleFrame":
        return Kernel().worker.getFrame("FightBattleFrame")

    @property
    def partyFrame(self) -> "BotPartyFrame":
        return Kernel().worker.getFrame("BotPartyFrame")

    def pulled(self) -> bool:
        self._enabled = False
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

    def findPathToTarget(self, spellw: SpellWrapper, targets: list[_Target]) -> Tuple[_Target, list[int]]:
        """
        Find path to the closest ldv to hit a mob.
        :param origin: position of the character
        :param po: max range of the spell
        :param targets: positions of the mobs
        :return: cell of the mob, path to the ldv if any else None
        """
        Logger().debug(
            f"entities positions : {[entity.disposition.cellId for entity in self.entitiesFrame.entities.values()]}"
        )
        Logger().debug(f"entities ids : {[entity.contextualId for entity in self.entitiesFrame.entities.values()]}")
        if not targets:
            if self.VERBOSE:
                Logger().debug("[FightAlgo] Not hittable target found")
            return None, None
        for target in targets:
            if target.pos.distanceTo(self.fighterPos) == 1.0:
                return target, []
        spellZone = self.getSpellZone(spellw)
        origin = self.fighterPos
        queue = collections.deque([[origin.cellId]])
        seen = {origin.cellId}
        while queue:
            path = queue.popleft()
            currCellId: int = path[-1]
            currSpellZone = spellZone.getCells(currCellId)
            ldv = set(LosDetector.getCell(DataMapProvider(), currSpellZone, currCellId))
            for target in targets:
                if target.pos.cellId in ldv:
                    return target, path[1:]
            currReachableCells = set(FightReachableCellsMaker(self.fighterInfos, currCellId, 1).reachableCells)
            for cellId in currReachableCells:
                if cellId not in seen:
                    queue.append(path + [cellId])
                    seen.add(cellId)
        if self.VERBOSE:
            Logger().debug(f"[FightAlgo] No valid path to reach a target found")
        return None, None

    def playTurn(self):
        targets = self.getTargetableEntities(self.spellw, targetSum=False)
        if not targets:
            targets = self.getTargetableEntities(self.spellw, targetSum=True)
            if not targets:
                self.addTurnAction(self.turnEnd, [])
                self.nextTurnAction()
                return
        if self.VERBOSE:
            Logger().info(f"[FightAlgo] MP : {self.movementPoints}, AP : {self.actionPoints}")
            Logger().info(f"[FightAlgo] Current attack spell : {self.spellw.spell.name}")
        self.updateReachableCells()
        target, path = self.findPathToTarget(self.spellw, targets)
        if target is not None:
            if len(path) == 0:
                if self.VERBOSE:
                    Logger().debug(f"[FightAlgo] Can hit target {target} from current position")
                self.addTurnAction(self.castSpell, [self.spellId, target.pos.cellId])
            elif path[-1] in self._reachableCells:
                if self.VERBOSE:
                    Logger().debug(
                        f"[FightAlgo] Last Path cell to target {target} is reachable will move to it before casting the spell"
                    )
                self.addTurnAction(self.askMove, [path])
                self.addTurnAction(self.castSpell, [self.spellId, target.pos.cellId])
            else:
                found = False
                for i, cellId in enumerate(path):
                    if cellId not in self._reachableCells:
                        if i != 0:
                            found = True
                            self.addTurnAction(self.askMove, [path[:i]])
                        break
                if self.VERBOSE:
                    Logger().debug(f"[FightAlgo] Have enough PM to get closer to the target ? {found}")
                self.addTurnAction(self.turnEnd, [])
        else:
            if self.VERBOSE:
                Logger().warn("[FightAlgo] No path to any target found")
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
        Logger().debug(f"[FightAlgo] Spell {spellw.spell.name} has range {range}")
        if spellw["rangeCanBeBoosted"]:
            range += playerStats.getStatTotalValue(StatIds.RANGE) - playerStats.getStatAdditionalValue(StatIds.RANGE)
        Logger().debug(f"[FightAlgo] Spell {spellw.spell.name} Range after apply of buffs is {range}")
        if range < minRange:
            range = minRange
        range = min(range, AtouinConstants.MAP_WIDTH * AtouinConstants.MAP_HEIGHT)
        if range < 0:
            range = 0
        return range

    def getSpellShape(self, spellw: SpellWrapper) -> int:
        spellShape: int = 0
        spellEffect: EffectInstance = None
        for spellEffect in spellw["effects"]:
            if spellEffect.zoneShape != 0 and (
                spellEffect.zoneSize > 0
                or spellEffect.zoneSize == 0
                and (spellEffect.zoneShape == SpellShapeEnum.P or spellEffect.zoneMinSize < 0)
            ):
                spellShape = spellEffect.zoneShape
        return spellShape

    def getSpellZone(self, spellw: SpellWrapper) -> IZone:
        range: int = self.getActualSpellRange(spellw)
        minRange: int = spellw.minimalRange
        spellShape: int = self.getSpellShape(spellw)
        castInLine: bool = spellw["castInLine"] or spellShape == SpellShapeEnum.l
        if castInLine and spellw["castInDiagonal"]:
            shapePlus = Cross(minRange, range, DataMapProvider())
            shapePlus.allDirections = True
            return shapePlus
        elif castInLine:
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
            BenchmarkTimer(1, self.nextTurnAction).start()
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
            if BotConfig().isLeader and not self._fightOptionsSent:
                gfotmsg = GameFightOptionToggleMessage()
                gfotmsg.init(FightOptionsEnum.FIGHT_OPTION_SET_SECRET)
                ConnectionsHandler().conn.send(gfotmsg)
                gfotmsg = GameFightOptionToggleMessage()
                gfotmsg.init(FightOptionsEnum.FIGHT_OPTION_SET_TO_PARTY_ONLY)
                ConnectionsHandler().conn.send(gfotmsg)
                self._fightOptionsSent = True
            return False

        elif isinstance(msg, GameFightEndMessage):
            self._inFight = False
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
            ConnectionsHandler().conn.send(startFightMsg)
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
        if self._repeatActionTimeout:
            self._repeatActionTimeout.cancel()
        if self.turnFrame:
            self.turnFrame.finishTurn()

    @property
    def fighterInfos(self) -> "GameContextActorInformations":
        info = self.entitiesFrame.getEntityInfos(CurrentPlayedFighterManager().currentFighterId)
        return info

    @property
    def fighterPos(self) -> "MapPoint":
        return MapPoint.fromCellId(self.fighterInfos.disposition.cellId)

    def getTargetableEntities(self, spellw: SpellWrapper, targetSum=False) -> list[_Target]:
        result = list[_Target]()
        if not FightEntitiesFrame.getCurrentInstance() or not self.battleFrame:
            return []
        if self.VERBOSE:
            Logger().debug(f"Deads list : {self.battleFrame._deadTurnsList}")
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
                    result.append(_Target(entity.contextualId, MapPoint.fromCellId(entity.disposition.cellId)))
        if self.VERBOSE:
            Logger().debug(f"[FightBot] Found targets : {[str(tgt) for tgt in result]}")
        return result

    def castSpell(self, spellId: int, cellId: bool) -> None:
        if self.VERBOSE:
            Logger().debug(f"[FightBot] Casting spell {spellId} on cell {cellId}.")
        gafcrmsg: GameActionFightCastRequestMessage = GameActionFightCastRequestMessage()
        gafcrmsg.init(spellId, cellId)
        ConnectionsHandler().conn.send(gafcrmsg)

    def askMove(self, cells: list[int], cellsTackled: list[int] = []) -> None:
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
