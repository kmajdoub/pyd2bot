from enum import Enum
from time import perf_counter

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import ChangeMap
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import \
    MovementFailError
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import \
    AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
    Edge
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

    def __init__(self):
        super().__init__()
        self.path = None
        self.state = AutoTripState.IDLE
        self.dstMapId = None
        self.dstRpZone = None
        self._nbr_follow_edge_fails = 0

    def run(self, dstMapId, dstZoneId=None, path: list[Edge] = None):
        self.dstMapId = dstMapId
        self.dstRpZone = dstZoneId
        if self.dstRpZone is not None:
            self.destVertex = WorldGraph().getVertex(self.dstMapId, self.dstRpZone)
            if self.destVertex is None:
                Logger().warning(f"Destination vertex not found for map {self.dstMapId} and zone {self.dstRpZone}")
        self.path = path
        AStar().resetForbinedEdges()
        self.walkToNextStep()

    def currentEdgeIndex(self):
        v = PlayedCharacterManager().currVertex
        for i, step in enumerate(self.path):
            if step.src.UID == v.UID:
                return i

    def onNextmapProcessed(self, code, error):
        if error:
            currentIndex = self.currentEdgeIndex()
            nextEdge = self.path[currentIndex]
            if code in [
                ChangeMap.INVALID_TRANSITION,
                MovementFailError.CANT_REACH_DEST_CELL,
                MovementFailError.MAPCHANGE_TIMEOUT,
                MovementFailError.NO_VALID_SCROLL_CELL,
                MovementFailError.INVALID_TRANSITION,
            ]:
                Logger().warning(f"Can't reach next step in found path for reason : {code}, {error}")
                
                if self._nbr_follow_edge_fails >= 3:
                    Logger().debug("Exceeded max number of fails, will ignore this edge.")
                    AStar().addForbidenEdge(nextEdge)
                    return self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResul)

                def retry(code, err):
                    if err:
                        return self.finish(code, err)
                    self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResul)
                    
                self._nbr_follow_edge_fails += 1
                return self.requestMapData(callback=retry)
            else:
                Logger().debug(f"Error while auto travelling : {error}")
                return self.finish(code, error)
        self._nbr_follow_edge_fails = 0
        self.walkToNextStep()

    def walkToNextStep(self, event_id=None):
        if PlayedCharacterManager().currentMap is None:
            Logger().warning("Waiting for Map to be processed...")
            return KernelEventsManager().onceMapProcessed(self.walkToNextStep, originator=self)
        if self.path:
            self.state = AutoTripState.FOLLOWING_EDGE
            currMapId = PlayedCharacterManager().currentMap.mapId
            currZoneId = PlayedCharacterManager().currentZoneRp
            dstMapId = self.path[-1].dst.mapId
            dstZoneId = self.path[-1].dst.zoneId
            if (not self.dstRpZone and currMapId == dstMapId) or (self.dstRpZone and currMapId == dstMapId and currZoneId == dstZoneId):
                Logger().info(f"Trip reached destination Map : {dstMapId}")
                return self.finish(True, None)
            currentIndex = self.currentEdgeIndex()
            if currentIndex is None:
                return self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResul)
            Logger().debug(f"Current step index: {currentIndex + 1}/{len(self.path)}")
            nextEdge = self.path[currentIndex]
            Logger().debug(f"Moving using next edge :")
            Logger().debug(f"\t|- src {nextEdge.src.mapId} -> dst {nextEdge.dst.mapId}")
            for tr in nextEdge.transitions:
                Logger().debug(f"\t| => {tr}")
            self.changeMap(edge=nextEdge, callback=self.onNextmapProcessed)
        else:
            self.state = AutoTripState.CALCULATING_PATH
            self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResul)

    def onPathFindResul(self, code, error, path):
        if error:
            return self.finish(code, error)
        if len(path) == 0:
            Logger().debug(f"Empty path found")
            return self.finish(True, None)
        for e in path:
            Logger().debug(f"\t|- src {e.src.mapId} -> dst {e.dst.mapId}")
            for tr in e.transitions:
                Logger().debug(f"\t\t|- {tr}")
        self.path = path
        self.walkToNextStep()

    def findPath(self, dstMapId, linkedZone, callback) -> None:
        src = PlayedCharacterManager().currVertex
        if src is None:
            return self.onceMapProcessed(self.findPath, [dstMapId, linkedZone, callback])
        Logger().info(f"Start searching path from {src} to destMapId {dstMapId}, linkedZone {linkedZone}")
        if linkedZone is None and PlayedCharacterManager().currentMap.mapId == dstMapId:
            return callback(0, None, [])
        if linkedZone is None:
            verticies = WorldGraph().getVertices(dstMapId).values()
        else:
            verticies = [WorldGraph().getVertex(dstMapId, linkedZone)]
        for dest_vertex in verticies:
            start = perf_counter()
            path = AStar().search(WorldGraph(), src, dest_vertex)
            if path is not None:
                Logger().info(f"Path to map {str(dstMapId)} found in {perf_counter() - start}s")
                callback(0, None, path)
                return
        callback(self.NO_PATH_FOUND, f"Unable to find path to dest map", None)

    def getState(self):
        return self.state.name
