import random
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from time import perf_counter, sleep
from typing import TYPE_CHECKING
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import MapPosition
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import (
    PlayedCharacterManager,
)
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import (
    InteractiveElementData,
)
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge

from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import (
    TransitionTypeEnum,
)

from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldPathFinder import (
    WorldPathFinder,
)

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import (
        RoleplayInteractivesFrame,
    )
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import (
        RoleplayMovementFrame,
    )

from pydofus2.com.ankamagames.atouin.messages.AdjacentMapClickMessage import (
    AdjacentMapClickMessage,
)
from pydofus2.com.ankamagames.atouin.messages.CellClickMessage import CellClickMessage
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.enums.DirectionsEnum import DirectionsEnum




class MapChange:
    def __init__(self, mapId, outCellId):
        self.destMapId = mapId
        self.outCellId = outCellId


class MoveAPI:
    
    @classmethod
    def randomMapChange(cls, discard=[]):
        transitions = cls.getOutGoingTransitions(discard)
        if len(transitions) == 0:
            raise Exception("Nbr of possible map change direction")
        Logger().debug("Nbr of Possible directions: %d", len(transitions))
        randTransition = random.choice(transitions)
        if randTransition.skillId > 0:
            rplInteractivesFrame: "RoleplayInteractivesFrame" = (
                Kernel().worker.getFrame("RoleplayInteractivesFrame")
            )
            ie = rplInteractivesFrame.interactives.get(randTransition.id)
            if ie is None:
                raise Exception(f"[MouvementAPI] InteractiveElement {randTransition.id} not found")
            Logger().debug(
                f"[MouvementAPI] Activating skill {randTransition.skillId} to change map towards '{randTransition.transitionMapId}'"
            )
            rplInteractivesFrame.skillClicked(ie)
        else:
            Logger().debug(
                f"[MouvementAPI] Sending a click to change map towards direction '{randTransition.transitionMapId}'"
            )
            cls.sendClickAdjacentMsg(randTransition.transitionMapId, randTransition.cell)
        return randTransition.transitionMapId, randTransition.skillId

    @classmethod
    def getOutGoingTransitions(
        cls, discard=[], noskill=True, directions: list[DirectionsEnum] = [], mapIds=[]
    ) -> list[Transition]:
        result = []
        v = WorldPathFinder().currPlayerVertex
        Logger().debug(f"current map {v.mapId}")
        outgoingEdges = WorldPathFinder().worldGraph.getOutgoingEdgesFromVertex(v)
        for e in outgoingEdges:
            if e.dst.mapId in discard:
                continue
            for tr in e.transitions:
                if noskill and tr.skillId > 0:
                    continue
                if directions and (tr.direction < 0 or DirectionsEnum(tr.direction) not in directions):
                    continue
                if mapIds and tr.transitionMapId not in mapIds:
                    continue
                result.append(tr)
        return result

    @classmethod
    def sendClickAdjacentMsg(cls, mapId: float, cellId: int) -> None:
        msg: AdjacentMapClickMessage = AdjacentMapClickMessage()
        msg.cellId = cellId
        msg.adjacentMapId = mapId
        Kernel().worker.process(msg)

    @classmethod
    def sendCellClickMsg(cls, mapId: float, cellId: int) -> None:
        msg: CellClickMessage = CellClickMessage()
        msg.cellId = cellId
        msg.id = mapId
        Kernel().worker.process(msg)

    @classmethod
    def changeMapToDstMapdId(cls, destMapId: int, discard=[]) -> None:
        transitions = cls.getOutGoingTransitions(discard=discard, mapIds=[destMapId])
        if len(transitions) == 0:
            raise Exception(f"No transition found towards mapId '{destMapId}'")
        cls.sendClickAdjacentMsg(transitions[0].transitionMapId, transitions[0].cell)

    @classmethod
    def followEdge(cls, edge: Edge):
        for tr in edge.transitions:
            if tr.isValid:
                cls.followTransition(tr)
                return True
        raise Exception("No valid transition found!!!")

    @classmethod
    def getTransitionIe(cls, transition: Transition) -> "InteractiveElementData":
        rpframe: "RoleplayInteractivesFrame" = Kernel().worker.getFrame("RoleplayInteractivesFrame")
        if not rpframe:
            BenchmarkTimer(1, cls.getTransitionIe, [transition]).start()
            return
        ie = rpframe.getInteractiveElement(transition.id, transition.skillId)
        if ie is not None:
            Logger().debug(f"[RolePlayMovement] InteractiveElement found: '{ie.element.elementId}'")
        else:
            Logger().warning(f"[RolePlayMovement] InteractiveElement not found: '{transition.skillId}' - retrying...")
            s = perf_counter()
            while True:
                if perf_counter() - s > 10:
                    raise Exception(f"[RolePlayMovement] InteractiveElement not found: '{transition.skillId}'")
                ie = cls.getTransitionIe(transition)
                if ie is not None:
                    break
                sleep(0.2)
            Logger().debug(f"[RolePlayMovement] InteractiveElement found: '{ie.element.elementId}' after retry")
        return ie

    @classmethod
    def followTransition(cls, tr: Transition):
        if not tr.isValid:
            raise Exception("[RolePlayMovement] Trying to follow a NON valid transition")
        if tr.transitionMapId == PlayedCharacterManager().currentMap.mapId:
            Logger().warning(
                f"[RolePlayMovement] transition is heading to my current map '{tr.transitionMapId}', nothing to do."
            )
            return True
        if TransitionTypeEnum(tr.type) == TransitionTypeEnum.INTERACTIVE:
            Logger().debug(
                f"[RolePlayMovement] Wants to activate skill '{tr.skillId}' to change map to '{tr.transitionMapId}'"
            )
            ie = cls.getTransitionIe(tr)
            rpmframe: "RoleplayMovementFrame" = Kernel().worker.getFrame("RoleplayMovementFrame")
            if tr.cell != PlayedCharacterManager().entity.position.cellId:
                rpmframe.setFollowingInteraction(
                    {
                        "ie": ie.element,
                        "skillInstanceId": int(ie.skillUID),
                        "additionalParam": 0,
                    }
                )
                rpmframe.resetNextMoveMapChange()
                rpmframe.askMoveTo(ie.position, TransitionTypeEnum.INTERACTIVE)
            else:
                rpmframe.activateSkill(ie.skillUID, tr.id, 0)
        else:
            Logger().debug(f"[RolePlayMovement] Scroll MAP change towards '{tr.transitionMapId}'")
            cls.sendClickAdjacentMsg(tr.transitionMapId, tr.cell)

    @classmethod
    def neighborMapIdFromcoords(cls, x: int, y: int) -> int:
        v = WorldPathFinder().currPlayerVertex
        if not v:
            BenchmarkTimer(1, cls.neighborMapIdFromcoords, [x, y]).start()
            return
        outgoingEdges = WorldPathFinder().worldGraph.getOutgoingEdgesFromVertex(v)
        for edge in outgoingEdges:
            mp = MapPosition.getMapPositionById(edge.dst.mapId)
            if mp.posX == x and mp.posY == y:
                for tr in edge.transitions:
                    if tr.isValid:
                        return tr.transitionMapId

    @classmethod
    def changeMapToDstCoords(cls, x: int, y: int) -> None:
        v = WorldPathFinder().currPlayerVertex
        if not v:
            BenchmarkTimer(1, cls.changeMapToDstCoords, [x, y]).start()
            return
        outgoingEdges = WorldPathFinder().worldGraph.getOutgoingEdgesFromVertex(v)
        for edge in outgoingEdges:
            mp = MapPosition.getMapPositionById(edge.dst.mapId)
            if mp.posX == x and mp.posY == y:
                for tr in edge.transitions:
                    if tr.isValid:
                        cls.followTransition(tr)
                        return True
        raise Exception("No valid transition found!!!")
