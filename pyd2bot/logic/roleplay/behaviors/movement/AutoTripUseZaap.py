from typing import Tuple, Optional, List
from dataclasses import dataclass

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.teleport.EnterHavenBag import EnterHavenBag
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.logic.roleplay.behaviors.teleport.UseZaap import UseZaap
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import MapPosition
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.dofus.uiApi.PlayedCharacterApi import PlayedCharacterApi
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.mapTools import MapTools

@dataclass
class TravelPlan:
    """Represents a complete travel plan using zaaps and/or walking"""
    src_zaap: Optional[Vertex] = None
    dst_zaap: Optional[Vertex] = None
    path_to_src_zaap: Optional[List[Edge]] = None
    path_from_dst_zaap: Optional[List[Edge]] = None
    direct_path: Optional[List[Edge]] = None
    total_cost: float = float('inf')
    total_steps: int = 0
    use_havenbag: bool = False

class AutoTripUseZaap(AbstractBehavior):
    NO_ASSOCIATED_ZAAP = 996555
    NO_PATH_TO_DEST = 665443
    DST_VERTEX_NOT_FOUND = 887744
    BOT_BUSY = 8877444
    ZAAP_HINT_CATEGORY = 9

    def __init__(self) -> None:
        self._wants_to_use_havenbag = False
        self._path_index = 0
        self.travel_plan = None
        self.teleportCostFromCurrToDstMap = float('inf')  # Initialize the attribute
        super().__init__()

    @property
    def currMapId(self):
        return PlayedCharacterManager().currentMap.mapId

    def run(
        self,
        dstMapId,
        dstZoneId,
        dstZaapMapId,
        withSaveZaap=False,
        maxCost=float("inf"),
    ):
        if not dstMapId:
            raise ValueError(f"Invalid MapId value {dstMapId}!")
            
        self.maxCost = min(maxCost, PlayedCharacterApi.inventoryKamas())
        self.dstMapId = dstMapId
        self.dstZoneId = dstZoneId
        self.withSaveZaap = withSaveZaap
        self.dstZaapMapId = dstZaapMapId
        
        self.on(KernelEvent.ServerTextInfo, self.onServerInfo)
        
        # Calculate teleport cost here before we use it
        self.teleportCostFromCurrToDstMap = 10 * MapTools.distL2Maps(self.currMapId, self.dstZaapMapId)
        Logger().debug(f"Teleport cost to destination: {self.teleportCostFromCurrToDstMap}")

        # Find best travel plan
        self.travel_plan = self.findBestTravelPlan()
        if not self.travel_plan:
            return self.finish(
                self.NO_PATH_TO_DEST,
                f"No valid path found to destination {self.dstMapId}!"
            )

        # Execute the travel plan
        self.executeTravelPlan()

    def findBestTravelPlan(self) -> Optional[TravelPlan]:
        """Find the best possible way to reach the destination"""
        plans = []

        # Try direct path first
        direct_plan = self.findDirectPath()
        if direct_plan:
            plans.append(direct_plan)

        # Try zaap-based path
        zaap_plan = self.findZaapBasedPath()
        if zaap_plan:
            plans.append(zaap_plan)

        # Try havenbag-based path if possible
        if self.canUseHavenBag():
            havenbag_plan = self.findHavenbagBasedPath()
            if havenbag_plan:
                plans.append(havenbag_plan)

        if not plans:
            return None

        # Return the plan with lowest total steps
        return min(plans, key=lambda p: p.total_steps)

    def findDirectPath(self) -> Optional[TravelPlan]:
        """Attempt to find a direct walking path to destination"""
        if self.dstZoneId is None:
            dst_vertex, path = self.findDestVertex(
                PlayedCharacterManager().currVertex, self.dstMapId
            )
        else:
            dst_vertex = WorldGraph().getVertex(self.dstMapId, self.dstZoneId)
            if not dst_vertex:
                return None
            _, path = self.findTravelInfos(
                dst_vertex, src_vertex=PlayedCharacterManager().currVertex
            )
        
        if not path:
            return None

        return TravelPlan(
            direct_path=path,
            total_steps=len(path)
        )

    def findZaapBasedPath(self) -> Optional[TravelPlan]:
        """Find a path using zaaps"""
        # Find nearest zaap to current position
        path_to_src_zaap = Localizer.findPathToClosestZaap(
            self.currMapId, self.maxCost, self.dstZaapMapId
        )
        if not path_to_src_zaap:
            return None

        src_zaap = path_to_src_zaap[-1].dst

        # Find path from destination zaap
        dst_vertex = WorldGraph().getVertex(self.dstMapId, self.dstZoneId or 1)
        if not dst_vertex:
            return None

        dst_zaap = WorldGraph().getVertex(self.dstZaapMapId, 1)
        if not dst_zaap:
            return None

        _, path_from_dst_zaap = self.findTravelInfos(dst_vertex, src_vertex=dst_zaap)
        if not path_from_dst_zaap:
            return None

        # Calculate total cost
        teleport_cost = 10 * MapTools.distL2Maps(src_zaap.mapId, dst_zaap.mapId)
        if teleport_cost > self.maxCost:
            return None

        return TravelPlan(
            src_zaap=src_zaap,
            dst_zaap=dst_zaap,
            path_to_src_zaap=path_to_src_zaap,
            path_from_dst_zaap=path_from_dst_zaap,
            total_cost=teleport_cost,
            total_steps=len(path_to_src_zaap) + len(path_from_dst_zaap)
        )

    def findHavenbagBasedPath(self) -> Optional[TravelPlan]:
        """Find a path using havenbag"""
        direct_path = self.findDirectPath()
        if not direct_path or not direct_path.direct_path:
            return None

        # Look for a suitable teleport point along the path
        for i, edge in enumerate(direct_path.direct_path):
            if not MapPosition.getMapPositionById(edge.src.mapId).allowTeleportFrom:
                continue

            teleport_cost = 10 * MapTools.distL2Maps(edge.src.mapId, self.dstZaapMapId)
            if teleport_cost > self.maxCost:
                continue

            dst_zaap = WorldGraph().getVertex(self.dstZaapMapId, 1)
            if not dst_zaap:
                continue

            _, path_from_dst = self.findTravelInfos(
                WorldGraph().getVertex(self.dstMapId, self.dstZoneId or 1),
                src_vertex=dst_zaap
            )
            if not path_from_dst:
                continue

            return TravelPlan(
                src_zaap=edge.src,
                dst_zaap=dst_zaap,
                path_to_src_zaap=direct_path.direct_path[:i],
                path_from_dst_zaap=path_from_dst,
                total_cost=teleport_cost,
                total_steps=i + len(path_from_dst),
                use_havenbag=True
            )
        return None

    def executeTravelPlan(self):
        """Execute the current travel plan"""
        if self.travel_plan.direct_path:
            Logger().debug("Executing direct path plan")
            self.autoTrip(
                self.dstMapId,
                self.dstZoneId,
                path=self.travel_plan.direct_path,
                callback=self.finish
            )
            return

        self._wants_to_use_havenbag = self.travel_plan.use_havenbag

        # Using zaaps or havenbag
        if self.travel_plan.path_to_src_zaap:
            Logger().debug("Moving to source zaap/teleport point")
            self.autoTrip(
                self.travel_plan.src_zaap.mapId,
                self.travel_plan.src_zaap.zoneId,
                path=self.travel_plan.path_to_src_zaap,
                callback=self.onSrcZaapReached
            )
        else:
            self.onSrcZaapReached(0, None)

    def canUseHavenBag(self):
        return (
            not PlayerManager().isBasicAccount()
            and PlayedCharacterManager().infos.level >= 10
            and self.teleportCostFromCurrToDstMap <= self.maxCost
        )

    def onServerInfo(self, event, msgId, msgType, textId, msgContent, params):
        if textId == 592304:  # Player is busy
            self.finish(self.BOT_BUSY, "Player is busy so we cant use zaap and walking might raise unexpected errors!")

    def onInsideHavenbag(self, code, err):
        if err:
            if code == EnterHavenBag.CANT_USE_IN_CURRENT_MAP:
                Logger().warning("Cannot use havenbag from current map, trying alternative path")
                if self.travel_plan.direct_path:
                    self.autoTrip(
                        self.dstMapId,
                        self.dstZoneId,
                        path=self.travel_plan.direct_path,
                        callback=self.finish
                    )
                else:
                    self.finish(code, "Cannot use havenbag and no alternative path available")
            else:
                self.finish(code, err)
        else:
            self.useZaap(
                self.travel_plan.dst_zaap.mapId,
                callback=self.onDstZaapReached
            )

    def onSrcZaapReached(self, code, err):
        """Handler for reaching source zaap"""
        if err:
            return self.finish(code, err)

        if self._wants_to_use_havenbag:
            self.enterHavenBag(wanted_state=True, callback=self.onInsideHavenbag)
            return

        zaapIe = Kernel().interactiveFrame.getZaapIe()
        if not zaapIe:
            return self.finish(
                UseSkill.UNREACHABLE_IE,
                "Cannot find zaap interactive element"
            )

        self.useZaap(
            self.travel_plan.dst_zaap.mapId,
            callback=self.onDstZaapReached
        )

    def onDstZaapReached(self, code=0, err=None):
        if err:
            if code == UseZaap.NOT_RICH_ENOUGH:
                Logger().warning("Not enough kamas for zaap, trying alternative path")
                if self.travel_plan.direct_path:
                    self.autoTrip(
                        self.dstMapId,
                        self.dstZoneId,
                        path=self.travel_plan.direct_path,
                        callback=self.finish
                    )
                else:
                    self.finish(code, err)
                return

            elif code in [UseZaap.DST_ZAAP_NOT_KNOWN, UseZaap.ZAAP_USE_ERROR]:
                Logger().warning(f"Zaap error: {err}")
                if self.travel_plan.direct_path:
                    self.autoTrip(
                        self.dstMapId,
                        self.dstZoneId,
                        path=self.travel_plan.direct_path,
                        callback=self.finish
                    )
                else:
                    self.finish(code, err)
                return

            return self.finish(code, err)

        if self.withSaveZaap:
            self.saveZaap(self.onDstZaapSaved)
        else:
            self.travelToDestOnFeet()

    def onDstZaapSaved(self, code, err):
        if err:
            return self.finish(code, err)
        self.travelToDestOnFeet()

    def travelToDestOnFeet(self):
        """Travel from destination zaap to final destination"""
        if not self.travel_plan.path_from_dst_zaap:
            Logger().warning("No path from destination zaap to final destination")
            return self.finish(
                self.NO_PATH_TO_DEST,
                "Cannot reach final destination from zaap"
            )

        self.autoTrip(
            self.dstMapId,
            self.dstZoneId,
            path=self.travel_plan.path_from_dst_zaap,
            callback=self.finish
        )

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
                path = AStar().search(WorldGraph(), src_vertex, dst_vertex, maxPathLength=min(maxLen, minDist))
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
                
            path = AStar().search(WorldGraph(), src_vertex, dst_vertex, maxPathLength=maxLen)
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
                
            path = AStar().search(WorldGraph(), src_vertex, dst_vertex)
            if path is not None:
                return dst_vertex, path
                
            rpZ += 1
            
        return None, None

    def finish(self, code=0, error=None):
        """Clean up and finish behavior execution"""
        if error:
            Logger().warning(f"AutoTripUseZaap finished with error: {error}")
        else:
            Logger().debug("AutoTripUseZaap finished successfully")
            
        super().finish(code, error)