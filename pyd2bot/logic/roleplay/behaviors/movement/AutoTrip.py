from enum import Enum
from time import perf_counter

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import ChangeMap
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import \
    MovementFailError
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import \
    AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
    Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import TransitionTypeEnum
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class AutoTripState(Enum):
    IDLE = 0
    CALCULATING_PATH = 1
    FOLLOWING_EDGE = 2


class AutoTrip(AbstractBehavior):
    NO_PATH_FOUND = 2202203
    PLAYER_IN_COMBAT = 89090
    MAX_RETIES_COUNT = 2

    def __init__(self, farm_resources_on_way):
        super().__init__()
        self.path = None
        self.state = AutoTripState.IDLE
        self.dstMapId = None
        self.dstRpZone = None
        self._nbr_follow_edge_fails = 0
        self.farm_resources_on_way = farm_resources_on_way
        self._iteration = 0
        self._previous_vertex: Vertex = None
        self._edge_taken: Edge = None
        self._taken_transition: Transition = None

    def run(self, dstMapId, dstZoneId=None, path: list[Edge] = None):
        self.dstMapId = dstMapId
        self.dstRpZone = dstZoneId
        if self.dstRpZone is not None:
            self.destVertex = WorldGraph().getVertex(self.dstMapId, self.dstRpZone)
            if self.destVertex is None:
                Logger().warning(f"Destination vertex not found for map {self.dstMapId} and zone {self.dstRpZone}")
        self.path = path
        AStar().resetForbiddenEdges()
        self.walkToNextStep()

    def currentEdgeIndex(self):
        v = PlayedCharacterManager().currVertex
        if not v:
            return None

        for i, step in enumerate(self.path):
            if step.src.UID == v.UID:
                return i

        Logger().error("Unable to find current player vertex index in the path!")
        Logger().debug(f"Current vertex : {v}")
        Logger().debug(f"Path vertices sources: {[step.src for step in self.path]}")
        Logger().debug(f"Path vertices destinations: {[step.dst for step in self.path]}")

    def _on_transition_executed(self, code1, error1, transition=None):
        self._taken_transition = transition
        if not error1 and self.farm_resources_on_way:
            def _on_resources_collected(code2, error2):
                if error2:
                    return self.finish(code2, error2)

                self._next_step(code1, error1)

            self.collect_all_map_resources(callback=_on_resources_collected)
        else:
            self._next_step(code1, error1)
    
    def _next_step(self, code, error):
        if not error and (PlayedCharacterManager().currVertex != self._edge_taken.dst):
            code = ChangeMap.errors.INVALID_TRANSITION
            error = "Player didn't land on the expected edge!"
            if self._taken_transition and TransitionTypeEnum(self._taken_transition.type) in [ TransitionTypeEnum.ZAAP, TransitionTypeEnum.HAVEN_BAG_ZAAP]:
                Logger().warning("Player may have took a guessed zaap landing vertex!")

        if error:
            currentIndex = self.currentEdgeIndex()
            if currentIndex is None:
                KernelEventsManager().send(KernelEvent.ClientRestart, "restart cause couldn't find the player current index in the current path!")
                return

            nextEdge = self.path[currentIndex]
    
            if code in [
                ChangeMap.errors.INVALID_TRANSITION,
                MovementFailError.CANT_REACH_DEST_CELL,
                MovementFailError.MAP_CHANGE_TIMEOUT,
                MovementFailError.NO_VALID_SCROLL_CELL,
                MovementFailError.INVALID_TRANSITION,
            ]:
                Logger().warning(f"Can't reach next step in found path for reason : {code}, {error}")
                self._previous_vertex = None

                if self._nbr_follow_edge_fails >= self.MAX_RETIES_COUNT:
                    Logger().debug("Exceeded max number of fails, will ignore this edge.")
                    AStar().addForbiddenEdge(nextEdge)
                    return self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResult)

                self._nbr_follow_edge_fails += 1
                Logger().warning(f"Attempt {self._nbr_follow_edge_fails}/{self.MAX_RETIES_COUNT} auto trip to dest")
                return self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResult)
            else:
                Logger().debug(f"Error while auto traveling : {error}")
                return self.finish(code, error)
            
        self._nbr_follow_edge_fails = 0
        self.walkToNextStep()

    def walkToNextStep(self, event_id=None):
        if Kernel().worker._terminating.is_set():
            return

        if self._previous_vertex and self._previous_vertex == PlayedCharacterManager().currVertex:
            Logger().warning(f"Player previous vertex : {self._previous_vertex}")
            Logger().warning(f"Player current vertex : {PlayedCharacterManager().currVertex}")
            raise Exception("It seems we encountered a silent bug, player applied change map with success but stayed on same old vertex!")

        self._iteration += 1
        if self._iteration > 500:
            raise Exception("Something bad is happening it seems like we entered an infinite loop!")

        if self.path is not None:
            if len(self.path) == 0:
                Logger().debug("Player already at the destination nothing to do")
                return self.finish(0)

            self.state = AutoTripState.FOLLOWING_EDGE
            currMapId = PlayedCharacterManager().currentMap.mapId
            currZoneId = PlayedCharacterManager().currentZoneRp
            dstMapId = self.path[-1].dst.mapId
            dstZoneId = self.path[-1].dst.zoneId
            if (not self.dstRpZone and currMapId == dstMapId) or (self.dstRpZone and currMapId == dstMapId and currZoneId == dstZoneId):
                Logger().info(f"Trip reached destination Map : {dstMapId}")
                return self.finish(0)
            currentIndex = self.currentEdgeIndex()
            if currentIndex is None:
                self._previous_vertex = None
                return self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResult)
            Logger().debug(f"Current step index: {currentIndex + 1}/{len(self.path)}")
            nextEdge = self.path[currentIndex]
            Logger().debug(f"Moving using next edge :")
            Logger().debug(f"\t|- src {nextEdge.src} -> dst {nextEdge.dst}")
            for tr in nextEdge.transitions:
                Logger().debug(f"\t| => {tr}")
            self._edge_taken = nextEdge
            self._previous_vertex = PlayedCharacterManager().currVertex.copy()
            Logger().debug(f"Saved previous vertex : {self._previous_vertex}")
            self.changeMap(edge=nextEdge, callback=self._on_transition_executed)
        else:
            self.state = AutoTripState.CALCULATING_PATH
            self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResult)

    def onPathFindResult(self, code, error, path):
        if error:
            return self.finish(code, error)

        if len(path) == 0:
            Logger().debug("Empty path found")
            return self.finish(0)
            
        Logger().debug("Found path:")
        for i, edge in enumerate(path, 1):
            Logger().debug(f"Step {i}/{len(path)}:")
            Logger().debug(f"  From: {edge.src}")
            Logger().debug(f"  To:   {edge.dst}")
            if edge.transitions:
                Logger().debug("  Transitions:")
                for tr in edge.transitions:
                    Logger().debug(f"    - {tr}")
            Logger().debug("")  # Empty line between steps
            
        self.path = path
        self.walkToNextStep()

    def findPath(self, dstMapId, linkedZone, callback) -> None:
        src = PlayedCharacterManager().currVertex
        if src is None:
            return self.once_map_rendered(self.findPath, [dstMapId, linkedZone, callback])
        Logger().info(f"Start searching path from {src} to destMapId {dstMapId}, linkedZone {linkedZone}")
        if linkedZone is None and PlayedCharacterManager().currentMap.mapId == dstMapId:
            return callback(0, None, [])
        if linkedZone is None:
            vertices = WorldGraph().getVertices(dstMapId).values()
        else:
            vertices = [WorldGraph().getVertex(dstMapId, linkedZone)]
        for dest_vertex in vertices:
            start = perf_counter()
            path = AStar().search(WorldGraph(), src, dest_vertex)
            if path is not None:
                Logger().info(f"Path to map {str(dstMapId)} found in {perf_counter() - start}s")
                callback(0, None, path)
                return
        callback(self.NO_PATH_FOUND, f"Unable to find path to dest map", None)

    def getState(self):
        return self.state.name
