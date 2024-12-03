import json
import math
import os
from typing import Tuple

from pydofus2.com.ankamagames.dofus.datacenter.world.Hint import Hint
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import \
    MapPosition
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
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
    def findClosestBankAsync(
        cls,
        callback,
        excludeMaps: list[float] = None,
    ) -> tuple[list["Edge"], "BankInfos"]:
        if not excludeMaps:
            excludeMaps = []

        is_basic_account = PlayerManager().isBasicAccount()

        startVertex = PlayedCharacterManager().currVertex

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
        
            bank_vertices = WorldGraph().getVertices(bank_map_id).values()

            for vertex in bank_vertices:
                candidates.append(vertex)
                vertex_bank_map[vertex] = bank_info

        if not candidates:
            Logger().warning("Could not find any accessible bank from current position")
            return None, None
        
        def on_result(code, err, path):
            if err:
                return callback(code, err, None, None)

            if path is not None:
                if not path:
                    matching_bank_info = vertex_bank_map.get(startVertex)
                else:
                    dest_vertex = path[-1].dst
                    matching_bank_info = vertex_bank_map.get(dest_vertex)
                    
                if matching_bank_info:
                    return callback(0, None, path, BankInfos(**matching_bank_info))

            callback(code, err, None, None)

        return AStar().search_async(PlayedCharacterManager().currVertex, candidates, callback=on_result)

    @classmethod
    def findClosestHintMapByGfxAsync(
        cls,
        gfx,
        callback,
        excludeMaps=None
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
            return callback(0, f"Could not find any accessible candidate maps with GFX {gfx}", None)

        Logger().debug(f"Found {len(candidates)} accessible candidate maps for hint GFX {gfx}")
                
        return AStar().search_async(PlayedCharacterManager().currVertex, candidates, callback=callback)

    @classmethod
    def findPathToClosestZaapAsync(
        cls,
        callback,
        maxCost=float("inf"),
        dstZaapMapId=None,
        excludeMaps=None,
        onlyKnownZaap=True,
    ) -> list["Edge"]:
        if not excludeMaps:
            excludeMaps = []

        if dstZaapMapId:
            dmp = MapPosition.getMapPositionById(dstZaapMapId)
        
        # Collect all valid zaap candidates first
        candidates = []
        for mapId in Hint.getZaapMapIds():
            if onlyKnownZaap and not PlayedCharacterManager().isZaapKnown():
                continue
                
            if dstZaapMapId:
                cmp = MapPosition.getMapPositionById(mapId)
                cost = 10 * int(math.sqrt((dmp.posX - cmp.posX) ** 2 + (dmp.posY - cmp.posY) ** 2))
                if cost > min(PlayedCharacterManager().characteristics.kamas, maxCost):
                    continue
                    
            candidates.extend(list(WorldGraph().getVertices(mapId).values()))
        
        if not candidates:
            Logger().warning(f"Could not find a candidate zaap")
            return None
                
        return AStar().search_async(PlayedCharacterManager().currVertex, candidates, callback=callback)

    @classmethod
    def  findDestVertexAsync(cls, src_vertex, dst_mapId, callback, rpZ=1) -> Tuple[Vertex, list[Edge]]:
        Logger().debug(f"Looking for dest vertex in map {dst_mapId} with rpZ {rpZ}")
        dst_vertex = WorldGraph().getVertex(dst_mapId, rpZ)
        if not dst_vertex:
            return callback(0, None, None, None)
        
        def on_result(code, err, path):
            if err:
                return callback(code, err, dst_vertex, path)

            if path is not None:
                return callback(0, None, dst_vertex, path)
            
            Logger().debug(f"No path found for dest vertex in map {dst_vertex} and src {src_vertex}")
            Kernel().defer(lambda: cls.findDestVertexAsync(src_vertex, dst_mapId, callback, rpZ + 1))
    
        AStar().search_async(src_vertex, dst_vertex, callback=on_result)
