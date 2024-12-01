import json
import math
import os
from typing import Tuple

from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.dofus.datacenter.world.Hint import Hint
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import \
    MapPosition
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import \
    AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
    Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import \
    Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class BankInfos:
    def __init__(
        self,
        npcActionId: int,
        npcId: float,
        npcMapId: float,
        openBankReplyId: int,
        name: str = "undefined",
    ):
        self.name = name
        self.npcActionId = npcActionId
        self.npcId = npcId
        self.npcMapId = npcMapId
        self.questionsReplies = {-1: [openBankReplyId]}

    def to_json(self):
        return {
            "npcActionId": self.npcActionId,
            "npcId": self.npcId,
            "npcMapId": self.npcMapId,
            "questionsReplies": self.questionsReplies,
        }


class Localizer:
    BANK_GFX = 401

    _phenixByAreaId = dict[int, list]()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, "areaInfos.json"), "r") as f:
        AREA_INFOS: dict = json.load(f)
    with open(os.path.join(base_dir, "banks.json"), "r") as f:
        BANKS: dict = json.load(f)

    @classmethod
    def getBankInfos(cls) -> BankInfos:
        if PlayerManager().isBasicAccount():
            return BankInfos(**cls.BANKS["Astrub"])
        return BankInfos(**cls.BANKS["Bonta"])

    @classmethod
    def findClosestBank(
        cls,
        startMapId: float = None,
        maxCost: float = float("inf"),
        excludeMaps: list[float] = None,
        dstMapId: float = None
    ) -> tuple[list["Edge"], "BankInfos"]:
        """
        Find path to closest bank location.
        Handles account restrictions for basic/subscriber areas.
        
        Args:
            startMapId: Starting map ID
            maxCost: Maximum path cost to consider (default: infinite)
            excludeMaps: List of map IDs to exclude from search
            dstMapId: Optional target map ID to calculate costs against
            
        Returns:
            Tuple of (path edges list, bank info) or (None, None) if no path found.
            Path can be empty list if already at destination.
        """
        possible_start_vertices = None
        if not excludeMaps:
            excludeMaps = []

        Logger().debug(f"Searching for closest bank from map {startMapId}")
        
        if not startMapId:
            possible_start_vertices = [PlayedCharacterManager().currVertex]

        # Get destination map position if specified (for cost calculations)
        if dstMapId:
            dst_map_pos = MapPosition.getMapPositionById(dstMapId)

        # Get all possible starting vertices
        if not possible_start_vertices:
            possible_start_vertices = WorldGraph().getVertices(startMapId).values()
        
        if not possible_start_vertices:
            Logger().warning(f"Could not find any vertex for map {startMapId}")
            return None, None

        Logger().debug(f"Found {len(possible_start_vertices)} vertices for map {startMapId}")

        is_basic_account = PlayerManager().isBasicAccount()

        for startVertex in possible_start_vertices:
            # Dictionary to map vertices to their corresponding banks
            vertex_bank_map = {}
            candidates = []
            
            # Iterate through all bank locations from the JSON file
            for bank_name, bank_info in cls.BANKS.items():
                bank_map_id = bank_info["npcMapId"]
                
                # Skip excluded maps
                if bank_map_id in excludeMaps:
                    continue
                
                # Check account restrictions for the bank map
                if is_basic_account:
                    bank_subarea = SubArea.getSubAreaByMapId(bank_map_id)
                    if bank_subarea and not bank_subarea.basicAccountAllowed:
                        Logger().debug(f"Skipping subscriber-only bank in {bank_name} (basic account)")
                        continue
                
                # If we have a destination map, calculate cost based on manhattan distance
                if dstMapId:
                    current_map_pos = MapPosition.getMapPositionById(bank_map_id)
                    cost = 10 * int(math.sqrt(
                        (dst_map_pos.posX - current_map_pos.posX) ** 2 + 
                        (dst_map_pos.posY - current_map_pos.posY) ** 2
                    ))
                    if cost <= min(PlayedCharacterManager().characteristics.kamas, maxCost):
                        bank_vertices = WorldGraph().getVertices(bank_map_id).values()
                        # Filter vertices based on account type
                        for vertex in bank_vertices:
                            if is_basic_account:
                                dst_subarea = SubArea.getSubAreaByMapId(vertex.mapId)
                                if dst_subarea and not dst_subarea.basicAccountAllowed:
                                    continue
                            candidates.append(vertex)
                            vertex_bank_map[vertex] = bank_info
                else:
                    bank_vertices = WorldGraph().getVertices(bank_map_id).values()
                    # Filter vertices based on account type
                    for vertex in bank_vertices:
                        if is_basic_account:
                            dst_subarea = SubArea.getSubAreaByMapId(vertex.mapId)
                            if dst_subarea and not dst_subarea.basicAccountAllowed:
                                continue
                        candidates.append(vertex)
                        vertex_bank_map[vertex] = bank_info

            if not candidates:
                Logger().warning("Could not find any accessible bank locations")
                continue

            Logger().debug(f"Found {len(candidates)} accessible bank locations")
            
            # Find path to closest candidate ensuring path doesn't go through subscriber areas for basic accounts
            path = cls.findPathToClosestVertexCandidate(startVertex, candidates)
            if path is not None:  # Path found (could be empty if at destination)
                if not path:  # Empty path means we're at destination
                    # Find which bank this vertex belongs to
                    matching_bank_info = vertex_bank_map.get(startVertex)
                else:
                    # Get the destination vertex from the path
                    dest_vertex = path[-1].dst
                    matching_bank_info = vertex_bank_map.get(dest_vertex)
                    
                if matching_bank_info:
                    return path, BankInfos(**matching_bank_info)

        return None, None

    @classmethod
    def phenixMapId(cls) -> float:
        subareaId = MapDisplayManager().currentDataMap.subareaId
        subarea = SubArea.getSubAreaById(subareaId)
        areaId = subarea._area.id
        return cls.AREA_INFOS[str(areaId)]["phoenix"]["mapId"]

    @classmethod
    def findClosestHintMapByGfx(
        cls,
        gfx,
        excludeMaps=None,
    ) -> list["Edge"]:
        if not excludeMaps:
            excludeMaps = []
        excludeMaps = list(map(int, excludeMaps))
        Logger().debug(f"Searching closest hint with GFX {gfx} from {PlayedCharacterManager().currVertex}")

        is_basic_account = PlayerManager().isBasicAccount()
        candidates = []
        
        for hint in Hint.getHints():
            if int(hint.mapId) in excludeMaps:
                continue
            
            if hint.gfx != gfx:
                continue
                
            if is_basic_account:
                hint_subarea = SubArea.getSubAreaByMapId(hint.mapId)
                if hint_subarea and not hint_subarea.basicAccountAllowed:
                    continue

            hint_vertices = WorldGraph().getVertices(hint.mapId).values()
            for vertex in hint_vertices:
                candidates.append(vertex)

        if not candidates:
            Logger().warning(f"Could not find any accessible candidate maps with GFX {gfx}")
            return None

        Logger().debug(f"Found {len(candidates)} accessible candidate maps for hint GFX {gfx}")
                
        return cls.findPathToClosestVertexCandidate(PlayedCharacterManager().currVertex, candidates)


    @classmethod
    def findPathToClosestZaap(
        cls,
        startMapId,
        maxCost=float("inf"),
        dstZaapMapId=None,
        excludeMaps=None,
        onlyKnownZaap=True,
    ) -> list["Edge"]:
        if not excludeMaps:
            excludeMaps = []
        Logger().debug(f"Searching closest zaap from map {startMapId}")
        if not startMapId:
            raise ValueError(f"Invalid mapId value {startMapId}")
            
        if dstZaapMapId:
            dmp = MapPosition.getMapPositionById(dstZaapMapId)
            
        possible_start_vertices = WorldGraph().getVertices(startMapId).values()
        if not possible_start_vertices:
            Logger().warning(f"Could not find any vertex for map {startMapId}")
            return None
        
        # Collect all valid zaap candidates first
        candidates = []
        for hint in Hint.getZaapMapIds():
            if hint.mapId in excludeMaps:
                continue

            if onlyKnownZaap and not PlayedCharacterManager().isZaapKnown(hint.mapId):
                continue
                
            if dstZaapMapId:
                cmp = MapPosition.getMapPositionById(hint.mapId)
                cost = 10 * int(math.sqrt((dmp.posX - cmp.posX) ** 2 + (dmp.posY - cmp.posY) ** 2))
                if cost > min(PlayedCharacterManager().characteristics.kamas, maxCost):
                    continue
                    
            candidates.extend(WorldGraph().getVertices(hint.mapId).values())
        
        if not candidates:
            Logger().warning(f"Could not find a candidate zaap for map {startMapId}")
            return None
        
        # Find shortest path from any start vertex
        shortest_path = None
        shortest_distance = float('inf')
        
        for startVertex in possible_start_vertices:
            path = cls.findPathToClosestVertexCandidate(startVertex, candidates)
            if (path is not None) and (shortest_path is None or len(path) < shortest_distance):
                shortest_path = path
                shortest_distance = len(path)
                
        return shortest_path

    @classmethod
    def findPathToClosestVertexCandidate(cls, vertex: Vertex, candidates: list[Vertex]) -> list["Edge"]:
        if not candidates:
            Logger().warning(f"No candidates to search path to!")
            return None
        path = AStar().search(vertex, candidates)
        if path is None:
            Logger().warning(f"Could not find a path to any of the candidates!")
            return None
        if len(path) == 0:
            Logger().warning(f"One of the candidates is the start map, returning it as closest map")
            return []
        return path

    @classmethod
    def findTravelInfos(
        cls, dst_vertex: Vertex, src_mapId=None, src_vertex=None, maxLen=float("inf")
    ) -> Tuple[Vertex, list[Edge]]:
        if dst_vertex is None:
            return None, None
            
        if src_vertex is None:
            if src_mapId == dst_vertex.mapId:
                return dst_vertex, []
                
            rpZ = 1
            minDist = float("inf")
            final_src_vertex = None
            final_path = None
            while True:
                src_vertex = WorldGraph().getVertex(src_mapId, rpZ)
                if not src_vertex:
                    break
                path = AStar().search(src_vertex, dst_vertex, maxPathLength=min(maxLen, minDist))
                if path is not None:
                    dist = len(path)
                    if dist < minDist:
                        minDist = dist
                        final_src_vertex = src_vertex
                        final_path = path
                rpZ += 1
            
            return final_src_vertex, final_path
        else:
            if src_vertex.mapId == dst_vertex.mapId:
                return src_vertex, []
                
            path = AStar().search(src_vertex, dst_vertex, maxPathLength=maxLen)
            if path is None:
                return None, None
                
            return src_vertex, path

    @classmethod
    def findDestVertex(cls, src_vertex, dst_mapId: int) -> Tuple[Vertex, list[Edge]]:
        """Find a vertex and path for the destination map"""
        rpZ = 1
        while True:
            Logger().debug(f"Looking for dest vertex in map {dst_mapId} with rpZ {rpZ}")
            dst_vertex = WorldGraph().getVertex(dst_mapId, rpZ)
            if not dst_vertex:
                break
                
            path = AStar().search(src_vertex, dst_vertex)
            if path is not None:
                return dst_vertex, path
            
            Logger().debug(f"No path found for dest vertex in map {dst_vertex} and src {src_vertex}")
            rpZ += 1
            
        return None, None
    
if __name__ == "__main__":
    Logger.logToConsole = True
    r = Localizer.findPathToClosestZaap(startMapId=128452097, onlyKnownZaap=False)
    endMapId = r[-1].dst.mapId
    print(f"Found path to closest zaap {endMapId} from map 128452097")
