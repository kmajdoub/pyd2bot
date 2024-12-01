from time import perf_counter
from typing import Optional

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class AstarPathFinder(AbstractBehavior):
    NO_PATH_FOUND = 2202203

    def __init__(self, dst_map_id: int, linked_zone: Optional[int]):
        super().__init__()
        self._start_time: float = 0
        self.dst_map_id = dst_map_id
        self.linked_zone = linked_zone

    def run(self, ) -> None:
        src = PlayedCharacterManager().currVertex
        if src is None:
            Logger().warning("Called path finder before player was added to the scene!")
            return self.once_map_rendered(self.run)
        
        Logger().info(f"Start searching path from {src} to destMapId {self.dst_map_id}, linkedZone {self.linked_zone}")
        
        if self.linked_zone is None and PlayedCharacterManager().currentMap.mapId == self.dst_map_id:
            return self.finish(0, None, [])
            
        if self.linked_zone is None:
            vertices = list(WorldGraph().getVertices(self.dst_map_id).values())
        else:
            vertex = WorldGraph().getVertex(self.dst_map_id, self.linked_zone)
            vertices = [vertex] if vertex else []

        if not vertices:
            return self.finish(self.NO_PATH_FOUND, "No valid destination vertices found", None)

        self.vertices = vertices
        self._start_time = perf_counter()
        src = PlayedCharacterManager().currVertex
        AStar().search_async(src, self.vertices, self._on_path_found_callback)

    def _on_path_found_callback(self, code, exc, path):
        search_time = perf_counter() - self._start_time
        Logger().info(f"Result found in {search_time}s")

        if code == 0:
            self.finish(0, None, path)
        else:
            self.finish(self.NO_PATH_FOUND, "Unable to find path to dest map", None)
