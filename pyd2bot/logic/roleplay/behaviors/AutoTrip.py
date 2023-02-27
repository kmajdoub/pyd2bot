from time import perf_counter
from typing import Tuple

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.ChangeMap import ChangeMap
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailReason import \
    MovementFailReason
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import \
    AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
    Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class AutoTrip(AbstractBehavior):
    
    def __init__(self):
        super().__init__()
        self.path = None
        
    def start(self, dstMapId, dstZoneId, callback):
        if self.running.is_set():
            return callback(False, "Autotrip already running")
        self.dstMapId = dstMapId
        self.dstRpZone = dstZoneId
        self.callback = callback
        self.path: list[Edge] = None
        self.running.set()
        self.walkToNextStep()

    def currentEdgeIndex(self):
        v = PlayedCharacterManager().currVertex
        for i, step in enumerate(self.path):
            if step.src == v:
                return i

    def walkToNextStep(self, event_id=None):
        if PlayedCharacterManager().currentMap is None:
            Logger().warning("[AutoTrip] Waiting for Map to be processed...")
            return KernelEventsManager().onceMapProcessed(self.walkToNextStep)
        if self.path:
            currMapId = PlayedCharacterManager().currVertex.mapId
            dstMapId = self.path[-1].dst.mapId
            if currMapId == dstMapId:
                Logger().info(f"[AutoTrip] Trip reached destination Map : {dstMapId}")
                return self.finish(True)
            currentIndex = self.currentEdgeIndex()
            if currentIndex is None:
                return self.finish(False, "Current player vertex not found in path")
            Logger().debug(f"[AutoTrip] Current step index: {currentIndex + 1}/{len(self.path)}")
            nextEdge = self.path[currentIndex]
            Logger().debug(f"[AutoTrip] Moving using next edge :")
            Logger().debug(f"\t|- src {nextEdge.src.mapId} -> dst {nextEdge.dst.mapId}")
            for tr in nextEdge.transitions:
                Logger().debug(f"\t\t|- direction : {tr.direction}, skill : {tr.skillId}, cell : {tr.cell}")
            def onProcessed(errType, error):
                if error:
                    if errType == MovementFailReason.CANT_REACH_DEST_CELL:
                        Logger().warning(f"[AutoTrip] Can't reach destination cell, retrying with another path...")
                        AStar().addForbidenEdge(nextEdge)
                        return self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResul)
                    else:
                        return self.finish(errType, error)
                self.walkToNextStep()
            ChangeMap().start(edge=nextEdge, callback=onProcessed)
        else:
            self.findPath(self.dstMapId, self.dstRpZone, self.onPathFindResul)
    
    def onPathFindResul(self, path, error):
        if error:
            return self.finish(path, error)
        if len(path) == 0:
            return self.finish(True, None)
        for e in path:
            Logger().debug(f"\t|- src {e.src.mapId} -> dst {e.dst.mapId}")
            for tr in e.transitions:
                Logger().debug(f"\t\t|- {tr}")
        self.path = path
        self.walkToNextStep()
        
    def findPath(self, dst: float, linkedZone: int, callback) -> None:
        if linkedZone is None:
            linkedZone = 1
        src = PlayedCharacterManager().currVertex
        if src is None:
            return KernelEventsManager().onceMapProcessed(self.findPath, [dst, linkedZone, callback])
        Logger().info(
            f"[WoldPathFinder] Start searching path from {src} to destMapId {dst}"
        )
        if int(PlayedCharacterManager().currentMap.mapId) == int(dst):
            return callback([], None)
        while True:        
            dstV = WorldGraph().getVertex(dst, linkedZone)            
            if dstV is None:
                Logger().warning(f"[WoldPathFinder] No vertex found for map {dst} and zone {linkedZone}!")
                return callback(None, "Unable to find path to dest map")
            start = perf_counter()
            path = AStar().search(WorldGraph(), src, dstV)
            if path:
                Logger().info(f"[WoldPathFinder] Path to map {str(dst)} found in {perf_counter() - start}s")
                return callback(path, None)
            linkedZone += 1
