import json
import os

from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import \
    AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph


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
        self.openBankReplyId = openBankReplyId

    def to_json(self):
        return {
            "npcActionId": self.npcActionId,
            "npcId": self.npcId,
            "npcMapId": self.npcMapId,
            "openBankReplyId": self.openBankReplyId,
        }

class Localizer:
    _phenixesByAreaId = dict[int, list]()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, "areaInfos.json"), "r") as f:
        AREAINFOS: dict = json.load(f)

    @classmethod
    def getBankInfos(cls) -> BankInfos:
        subareaId = MapDisplayManager().currentDataMap.subareaId
        subarea = SubArea.getSubAreaById(subareaId)
        areaId = subarea._area.id
        minDist = float("inf")
        srcV = PlayedCharacterManager().currVertex
        closestBank = cls.AREAINFOS[str(areaId)]["bank"][0]
        rpZ = 1
        for bank in cls.AREAINFOS[str(areaId)]["bank"][1:]:
            if bank["npcMapId"] == PlayedCharacterManager().currentMap.mapId:
                closestBank = bank["npcMapId"]
                break
            while True:
                dstV = WorldGraph().getVertex(bank["npcMapId"], rpZ)
                if not dstV:
                    break
                path = AStar().search(WorldGraph(), srcV, dstV, lambda x: (), False)
                if path is not None:
                    dist = len(path)
                    if dist < minDist:
                        minDist = dist
                        closestBank = bank
                    break
                rpZ += 1
        if closestBank is None:
            raise Exception(f"Could not find closest bank to areaId {areaId}")
        return BankInfos(**closestBank)

    @classmethod
    def phenixMapId(cls) -> float:
        subareaId = MapDisplayManager().currentDataMap.subareaId
        subarea = SubArea.getSubAreaById(subareaId)
        areaId = subarea._area.id
        return cls.AREAINFOS[str(areaId)]["phoenix"]["mapId"]
