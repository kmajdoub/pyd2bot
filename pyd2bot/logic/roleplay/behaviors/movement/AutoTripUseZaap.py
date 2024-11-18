from typing import Tuple, Optional, List
from dataclasses import dataclass

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.teleport.ToggleHavenBag import ToggleHavenBag
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.logic.roleplay.behaviors.teleport.UseZaap import UseZaap
from pyd2bot.misc.Localizer import Localizer
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
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
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
    havenbag_source_vertex: Optional[Vertex] = None
    path_to_havenbag_point: Optional[List[Edge]] = None

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
        farm_resources_on_way=False,
        maxCost=float("inf"),
    ):
        if not dstMapId:
            raise ValueError(f"Invalid MapId value {dstMapId}!")
            
        self.maxCost = min(maxCost, PlayedCharacterApi.inventoryKamas())
        self.dstMapId = dstMapId
        self.dstZoneId = dstZoneId
        self.withSaveZaap = withSaveZaap
        self.dstZaapMapId = dstZaapMapId
        self.farm_resources_on_way = farm_resources_on_way
        
        self.on(KernelEvent.ServerTextInfo, self.onServerInfo)
        
        # Calculate teleport cost here before we use it
        self.teleportCostFromCurrToDstMap = 10 * MapTools.distL2Maps(self.currMapId, self.dstZaapMapId)
        # Logger().debug(f"Teleport cost to destination: {self.teleportCostFromCurrToDstMap}")

        # Find best travel plan
        self.travel_plan = self.findBestTravelPlan()
        if self.travel_plan is None:
            return self.finish(
                self.NO_PATH_TO_DEST,
                f"No valid path found to destination {self.dstMapId}!"
            )

        # Execute the travel plan
        self.executeTravelPlan()

    def findHavenbagBasedPath(self) -> Optional[TravelPlan]:
        """Find a path using havenbag with proper navigation to teleport point"""
        direct_path_plan = self.findDirectPathPlan()
        if not direct_path_plan or direct_path_plan.direct_path is None:
            return None

        curr_vertex = PlayedCharacterManager().currVertex
        if not curr_vertex:
            return None

        # Look for a suitable teleport point along the path
        for i, edge in enumerate(direct_path_plan.direct_path):
            if not MapPosition.getMapPositionById(edge.src.mapId).allowTeleportFrom:
                continue

            teleport_cost = 10 * MapTools.distL2Maps(edge.src.mapId, self.dstZaapMapId)
            if teleport_cost > self.maxCost:
                continue

            dst_zaap = WorldGraph().getVertex(self.dstZaapMapId, 1)
            if not dst_zaap:
                continue

            # Find path to havenbag point
            path_to_point = None
            if edge.src.mapId != curr_vertex.mapId:
                _, path_to_point = self.findTravelInfos(edge.src, src_vertex=curr_vertex)
                if path_to_point is None:
                    continue

            _, path_from_dst = self.findTravelInfos(
                WorldGraph().getVertex(self.dstMapId, self.dstZoneId or 1),
                src_vertex=dst_zaap
            )
            if path_from_dst is None:
                continue

            total_steps = len(path_from_dst)
            if path_to_point is not None:
                total_steps += len(path_to_point)

            return TravelPlan(
                src_zaap=edge.src,
                dst_zaap=dst_zaap,
                path_from_dst_zaap=path_from_dst,
                total_cost=teleport_cost,
                total_steps=total_steps,
                use_havenbag=True,
                havenbag_source_vertex=edge.src,
                path_to_havenbag_point=path_to_point
            )
        return None

    def findBestTravelPlan(self) -> Optional[TravelPlan]:
        """Find the best possible way to reach the destination"""
        plans = []

        # Try direct path first
        direct_plan = self.findDirectPathPlan()
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

    def findDirectPathPlan(self) -> Optional[TravelPlan]:
        """Attempt to find a direct walking path to destination"""
        if self.dstZoneId is None:
            if PlayedCharacterManager().currVertex is None:
                Logger().warning(f"Current player vertex is not defined, we cant look for path!")

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
        
        if path is None:
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
        if path_to_src_zaap is None:
            return None
        
        if len(path_to_src_zaap) == 0:
            src_zaap = PlayedCharacterManager().currVertex
        else:
            src_zaap = path_to_src_zaap[-1].dst

        # Find path from destination zaap
        dst_vertex = WorldGraph().getVertex(self.dstMapId, self.dstZoneId or 1)
        if not dst_vertex:
            return None

        dst_zaap = WorldGraph().getVertex(self.dstZaapMapId, 1)
        if not dst_zaap:
            return None

        _, path_from_dst_zaap = self.findTravelInfos(dst_vertex, src_vertex=dst_zaap)
        if path_from_dst_zaap is None:
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

    def onHavenbagPointReached(self, code, err):
        """Handler for reaching havenbag teleport point"""
        if err:
            return self.finish(code, err)
            
        Logger().debug(f"Reached havenbag point at {self.travel_plan.havenbag_source_vertex.mapId}")
        self.toggle_haven_bag(wanted_state=True, callback=self.onInsideHavenbag)

    def executeTravelPlan(self):
        """Execute the current travel plan with proper havenbag point navigation"""
        if self.travel_plan.direct_path is not None:
            Logger().debug("Executing direct path plan")
            self.autoTrip(
                self.dstMapId,
                self.dstZoneId,
                path=self.travel_plan.direct_path,
                farm_resources_on_way=self.farm_resources_on_way,
                callback=self.finish
            )
            return

        self._wants_to_use_havenbag = self.travel_plan.use_havenbag

        if self._wants_to_use_havenbag:
            if self.travel_plan.path_to_havenbag_point is not None:
                Logger().debug("Moving to havenbag teleport point")
                self.autoTrip(
                    self.travel_plan.havenbag_source_vertex.mapId,
                    self.travel_plan.havenbag_source_vertex.zoneId,
                    path=self.travel_plan.path_to_havenbag_point,
                    farm_resources_on_way=self.farm_resources_on_way,
                    callback=self.onHavenbagPointReached
                )
            else:
                self.onHavenbagPointReached(0, None)
            return

        # Using zaaps
        if self.travel_plan.path_to_src_zaap is not None:
            Logger().debug("Moving to source zaap")
            self.autoTrip(
                self.travel_plan.src_zaap.mapId,
                self.travel_plan.src_zaap.zoneId,
                path=self.travel_plan.path_to_src_zaap,
                farm_resources_on_way=self.farm_resources_on_way,
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
            if code == ToggleHavenBag.CANT_USE_IN_CURRENT_MAP:
                Logger().warning("Cannot use havenbag from current map, trying alternative paths")
                
                # Reset havenbag flag to prevent loops
                self._wants_to_use_havenbag = False
            
                # Try zaap-based path first since it might be faster
                zaap_plan = self.findZaapBasedPath()
                if zaap_plan is not None:
                    Logger().debug("Using zaap as fallback path")
                    self.travel_plan = zaap_plan
                    if self.travel_plan.path_to_src_zaap is not None:
                        self.autoTrip(
                            self.travel_plan.src_zaap.mapId,
                            self.travel_plan.src_zaap.zoneId,
                            path=self.travel_plan.path_to_src_zaap,
                            farm_resources_on_way=self.farm_resources_on_way,
                            callback=self.onSrcZaapReached
                        )
                    else:
                        self.onSrcZaapReached(0, None)
                    return
                
                # If no zaap path, try direct path
                if self.travel_plan.direct_path is not None:
                    Logger().debug("Using direct path as fallback")
                    self.autoTrip(
                        self.dstMapId,
                        self.dstZoneId,
                        path=self.travel_plan.direct_path,
                        farm_resources_on_way=self.farm_resources_on_way,
                        callback=self.finish
                    )
                else:
                    self.finish(code, "No alternative paths available after havenbag failed")
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
            self.toggle_haven_bag(wanted_state=True, callback=self.onInsideHavenbag)
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
            if code == UseZaap.INSUFFICIENT_KAMAS:
                Logger().warning("Not enough kamas for zaap, trying alternative path")
                if self.travel_plan.direct_path:
                    self.autoTrip(
                        self.dstMapId,
                        self.dstZoneId,
                        path=self.travel_plan.direct_path,
                        farm_resources_on_way=self.farm_resources_on_way,
                        callback=self.finish
                    )
                else:
                    self.finish(code, err)
                return
            if code == UseZaap.ZAAP_USE_ERROR:
                direct_plan = self.findDirectPathPlan()  # Get fresh direct path
                if direct_plan and direct_plan.direct_path is not None:
                    Logger().debug("Found walking path as fallback for zaap use error")
                    self.travel_plan = direct_plan
                    self.autoTrip(
                        self.dstMapId,
                        self.dstZoneId,
                        path=self.travel_plan.direct_path,
                        farm_resources_on_way=self.farm_resources_on_way,
                        callback=self.finish
                    )
                else:
                    self.finish(code, f"Zaap use failed and no walking path available: {err}")
                return

            elif code in [UseZaap.DST_ZAAP_NOT_KNOWN, UseZaap.ZAAP_USE_ERROR]:
                Logger().warning(f"Zaap error: {err}")
                if self.travel_plan.direct_path is not None:
                    self.autoTrip(
                        self.dstMapId,
                        self.dstZoneId,
                        path=self.travel_plan.direct_path,
                        farm_resources_on_way=self.farm_resources_on_way,
                        callback=self.finish
                    )
                else:
                    self.finish(code, err)
                return

            return self.finish(code, err)

        if self.withSaveZaap:
            self.save_zaap(self.onDstZaapSaved)
        else:
            self.travelToDestOnFeet()

    def onDstZaapSaved(self, code, err):
        if err:
            return self.finish(code, err)
        self.travelToDestOnFeet()

    def travelToDestOnFeet(self):
        """Travel from destination zaap to final destination"""
        if self.travel_plan.path_from_dst_zaap is not None:
            Logger().warning("No path from destination zaap to final destination")
            return self.finish(
                self.NO_PATH_TO_DEST,
                "Cannot reach final destination from zaap"
            )

        self.autoTrip(
            self.dstMapId,
            self.dstZoneId,
            path=self.travel_plan.path_from_dst_zaap,
            farm_resources_on_way=self.farm_resources_on_way,
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
            
            Logger().debug(f"No path found for dest vertex in map {dst_vertex} and src {src_vertex}")
            rpZ += 1
            
        return None, None

    def finish(self, code=0, error=None):
        """Clean up and finish behavior execution"""
        if error:
            Logger().warning(f"AutoTripUseZaap finished with error: {error}")
        else:
            Logger().debug("AutoTripUseZaap finished successfully")
            
        super().finish(code, error)