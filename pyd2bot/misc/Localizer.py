import json
import math
import os

from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.dofus.datacenter.world.Hint import Hint
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import \
    MapPosition
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import \
    AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
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
        self.questionsReplies = { -1: [openBankReplyId] }

    def to_json(self):
        return {
            "npcActionId": self.npcActionId,
            "npcId": self.npcId,
            "npcMapId": self.npcMapId,
            "questionsReplies": self.questionsReplies,
        }


class Localizer:
    
    ZAAP_GFX = 410
    BANK_GFX = 401 
    
    _phenixesByAreaId = dict[int, list]()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, "areaInfos.json"), "r") as f:
        AREAINFOS: dict = json.load(f)
    with open(os.path.join(base_dir, "banks.json"), "r") as f:
        BANKS: dict = json.load(f)
        
    @classmethod
    def getBankInfos(cls) -> BankInfos:
        return BankInfos(**cls.BANKS["Astrub"])

    @classmethod
    def phenixMapId(cls) -> float:
        subareaId = MapDisplayManager().currentDataMap.subareaId
        subarea = SubArea.getSubAreaById(subareaId)
        areaId = subarea._area.id
        return cls.AREAINFOS[str(areaId)]["phoenix"]["mapId"]

    @classmethod
    def findClosestHintMapByGfx(cls, mapId, gfx):
        for startVertex in WorldGraph().getVertices(mapId).values():
            candidates = []
            for hint in Hint.getHints():
                if hint.gfx == gfx:
                    candidates.extend(WorldGraph().getVertices(hint.mapId).values())
            if not candidates:
                return None
            Logger().debug(f"Found {len(candidates)} candidates maps for closest map to hint {gfx}")  
            return AStar().search(WorldGraph(), startVertex, candidates)

    @classmethod
    def findPathtoClosestZaap(cls, startMapId, maxCost=float("inf"), dstZaapMapId=None, excludeMaps=[]) -> list['Edge']:
        Logger().debug(f"Searching closest zaap from map {startMapId}")
        if not startMapId:
            raise ValueError(f"Invalid mapId value {startMapId}")
        if dstZaapMapId:
            dmp = MapPosition.getMapPositionById(dstZaapMapId)
        for startVertex in WorldGraph().getVertices(startMapId).values():
            candidates = []
            for hint in Hint.getHints():
                if hint.mapId in excludeMaps:
                    continue
                if hint.gfx == cls.ZAAP_GFX:
                    if PlayedCharacterManager().isZaapKnown(hint.mapId):
                        if dstZaapMapId:
                            cmp = MapPosition.getMapPositionById(hint.mapId)
                            cost = 10 * int(math.sqrt((dmp.posX - cmp.posX)**2 + (dmp.posY - cmp.posY)**2))
                            if cost <= maxCost:
                                candidates.extend(WorldGraph().getVertices(hint.mapId).values())
                        else:
                            candidates.extend(WorldGraph().getVertices(hint.mapId).values())
            if not candidates:
                Logger().warning(f"Could not find a candidate zaap for map {startMapId}")
                return None, None
            Logger().debug(f"Found {len(candidates)} candidates maps for closest zaap to map {startMapId}")
            return cls.findPathtoClosestVertexFromVerticies(startVertex, candidates)
        return None
        
        
    @classmethod
    def findPathtoClosestVertexFromVerticies(cls, vertex: Vertex, candidates: list[Vertex]):
        Logger().info(f"Searching closest map from vertex to one of the candidates")
        if not candidates:
            Logger().warning(f"No candidates to search path to!")
            return None
        path = AStar().search(WorldGraph(), vertex, candidates)
        if path is None:
            Logger().warning(f"Could not find a path to any of the candidates!")
            return None
        if len(path) == 0:
            Logger().warning(f"One of the candidates is the start map, returning it as closest zaap")
            return []
        return path