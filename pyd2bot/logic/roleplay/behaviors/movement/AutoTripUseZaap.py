from typing import Tuple

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.movement.EnterHavenBag import EnterHavenBag
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.logic.roleplay.behaviors.teleport.UseZaap import UseZaap
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import \
    PlayerManager
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
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.mapTools import MapTools


class AutoTripUseZaap(AbstractBehavior):
    NOASSOCIATED_ZAAP = 996555
    BOT_BUSY = 8877444
    ZAAP_HINT_CAREGORY = 9

    _allZaapMapIds: list[int] = None

    def __init__(self) -> None:
        self.src_zaap_vertex = None
        self._wants_to_use_havenbag = False
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
        self.maxCost = maxCost
        self.dstMapId = dstMapId
        self.dstZoneId = dstZoneId
        self.withSaveZaap = withSaveZaap
        self.on(KernelEvent.ServerTextInfo, self.onServerInfo)
        self.dstZaapMapId = dstZaapMapId
        self.dstVertex = WorldGraph().getVertex(self.dstMapId, self.dstZoneId)
        self.dstZaapVertex, self.dist_from_dest_zaap_to_dest, self.path_from_dest_zaap_to_dest = self.findTravelInfos(
            self.dstVertex, src_mapId=self.dstZaapMapId
        )
        _, self.dist_from_currmap_to_dest, self.path_from_currmap_to_dest = self.findTravelInfos(
            self.dstVertex, src_vertex=PlayedCharacterManager().currVertex
        )
        self.teleportCostFromCurrToDstMap = 10 * MapTools.distL2Maps(
            self.currMapId, self.dstZaapMapId
        )
        Logger().debug(f"Player basic account: {PlayerManager().isBasicAccount()}")
        Logger().debug(
            f"Teleport cost to dest from curr pos is {self.teleportCostFromCurrToDstMap:.2f}, teleport max cost is {self.maxCost}."
        )
        Logger().debug(f"Distance from current Map to dest Zaap is {self.dist_from_currmap_to_dest} map steps away.")
        if self.canUseHavenBag(): # Here we check if we can't use havenbag to reach dest zaap
            Logger().debug(f"Player can use havenbag to reach dest zaap.")
            Logger().debug(f"Looking for a map we can use havenbag to reach dest zaap from.")
            for i, edge in enumerate(self.path_from_currmap_to_dest):
                teleport_cost = 10 * MapTools.distL2Maps(edge.src.mapId, self.dstZaapMapId)
                if teleport_cost <= self.maxCost:
                    self._wants_to_use_havenbag = True
                    self._path_index = i
                    self.src_zaap_vertex = edge.src
                    self.dist_from_currmap_to_src_zaap = i
                    self.path_from_currmap_to_src_zaap = self.path_from_currmap_to_dest[0:i] if i > 0 else []
                    Logger().debug(f"Found a map we can use havenbag to reach dest zaap from, map is {i} steps away.")
                    Logger().debug(
                        f"Walking dist = {self.dist_from_currmap_to_dest}, walking to src zap + walking to dst from dst Zaap = {self.dist_from_currmap_to_src_zaap + self.dist_from_dest_zaap_to_dest}"
                    )
                    if self.dist_from_currmap_to_dest <= self.dist_from_currmap_to_src_zaap + self.dist_from_dest_zaap_to_dest:
                        Logger().debug(f"Its better to walk to dest map directly.")
                        self.travelToDestinationOnFeetWithSaveZaap()
                        return
                    self.travelToSrcZaapOnFeet()
                    return
            Logger().debug(f"Can't use havenbag to reach dest zaap, will travel to src zaap on feet.")
            self.travelToDestinationOnFeetWithSaveZaap()
        else:
            self.path_from_currmap_to_src_zaap = Localizer.findPathtoClosestZaap(
                self.currMapId, self.maxCost, self.dstZaapMapId
            )
            if not self.path_from_currmap_to_src_zaap:
                Logger().warning(f"No associated ZAAP found for map {self.dstMapId}.")
                self.travelToDestinationOnFeetWithSaveZaap()
                return
            self.src_zaap_vertex = self.path_from_currmap_to_src_zaap[-1].dst
            self.dist_from_currmap_to_src_zaap = len(self.path_from_currmap_to_src_zaap)
            Logger().debug(f"Found src zaap at {self.dist_from_currmap_to_src_zaap} map steps from current pos.")
            Logger().debug(
                f"Walking dist = {self.dist_from_currmap_to_dest}, walking to src zap + walking to dst from dst Zaap = {self.dist_from_currmap_to_src_zaap + self.dist_from_dest_zaap_to_dest}"
            )
            if self.dist_from_currmap_to_dest <= self.dist_from_currmap_to_src_zaap + self.dist_from_dest_zaap_to_dest:
                Logger().debug(f"Its better to walk to dest map directly.")
                self.travelToDestinationOnFeetWithSaveZaap()
            else:
                self.travelToSrcZaapOnFeet()

    def onHavenBagUseSourceMap(self, code, err):
        pass
    
    def canUseHavenBag(self):
        return not PlayerManager().isBasicAccount() and PlayedCharacterManager().infos.level >= 10 and self.teleportCostFromCurrToDstMap <= self.maxCost
        
    def onServerInfo(self, event, msgId, msgType, textId, msgContent, params):
        if textId == 592304:  # Player is busy
            self.finish(
                self.BOT_BUSY,
                "Player is busy so we cant use zaap and walking might raise unexpected errors!!",
            )

    def travelToSrcZaapOnFeet(self):
        self.autoTrip(
            self.src_zaap_vertex.mapId,
            self.src_zaap_vertex.zoneId,
            path=self.path_from_currmap_to_src_zaap,
            callback=self.onSrcZaapTrip,
        )
        
    def onInsideHavenbag(self, code, err):
        if err:
            Logger().warning(
                f"Unable to use haven bag for reason {err}, so we will travel to destinaton on feet!"
            )
            if code == EnterHavenBag.CANT_USE_IN_CURRENT_MAP and self._wants_to_use_havenbag and self._path_index < len(self.path_from_currmap_to_dest):
                Logger().warning(f"Player can't use haven bag in current map, will try to use it in next map of path.")
                for i, edge in enumerate(self.path_from_currmap_to_dest[self._path_index + 1:]):
                    teleport_cost = 10 * MapTools.distL2Maps(edge.src.mapId, self.dstZaapMapId)
                    if teleport_cost <= self.maxCost:
                        self._wants_to_use_havenbag = True
                        self._path_index = i + self._path_index + 1
                        self.src_zaap_vertex = edge.src
                        self.dist_from_currmap_to_src_zaap = i
                        self.path_from_currmap_to_src_zaap = self.path_from_currmap_to_dest[self._path_index:self._path_index + 1 + i]
                        Logger().debug(f"Found a map we can use havenbag to reach dest zaap from, map is {i + 1} steps away.")
                        Logger().debug(
                            f"Walking dist = {self.dist_from_currmap_to_dest}, walking to src zap + walking to dst from dst Zaap = {self.dist_from_currmap_to_src_zaap + self.dist_from_dest_zaap_to_dest}"
                        )
                        if self.dist_from_currmap_to_dest <= self.dist_from_currmap_to_src_zaap + self.dist_from_dest_zaap_to_dest:
                            Logger().debug(f"Its better to walk to dest map directly.")
                            return self.travelToDestinationOnFeetWithSaveZaap()
                        return self.travelToSrcZaapOnFeet()
            Logger().error(f"Can't use haven bag in any map of path to reach dest zaap, will travel to it on feet.")
            self.travelToDestinationOnFeetWithSaveZaap()
        else:
            self.onSrcZaapTrip(True, None)

    def onDstZaapSaved(self, code, err):
        if err:
            return self.finish(code, err)
        self.travelToDestOnFeet()
    
    def onDstZaapReached(self):
        Logger().debug(f"Reached dest map!")
        if self.withSaveZaap:
            self.saveZaap(self.onDstZaapSaved)
        else:
            self.travelToDestOnFeet()

    def onDstZaap_feetTrip(self, code, err):
        if err:
            if code == AutoTrip.NO_PATH_FOUND:
                return self.onDstZaapUnreachable()
            return self.finish(code, err)
        self.onDstZaapReached()
            
    def travelToDstZaapOnFeet(self):
        self.autoTrip(self.dstZaapVertex.mapId, self.dstZaapVertex.zoneId, callback=self.onDstZaap_feetTrip)
    
    def travelToDestOnFeet(self):
        self.autoTrip(self.dstMapId, self.dstZoneId, callback=self.finish)
 
    def onDstZaapUnreachable(self):
        Logger().warning(
            "No path found to dest zaap will travel to dest map on feet"
        )
        return self.autoTrip(
            self.dstMapId, self.dstZoneId, callback=self.finish
        )
        
    def travelToDestinationOnFeetWithSaveZaap(self):
        if self.withSaveZaap:
            Logger().debug(f"Will trip to dest zaap at {self.dstZaapVertex.mapId} on feet to save it before travelling to dest on feet.")
            self.travelToDstZaapOnFeet()
        else:
            Logger().debug(f"Will auto trip on feet to dest")
            self.travelToDestOnFeet()
    
    def onDstZaap_zaapTrip(self, code, err, **kwargs):
        if err:
            if code == UseZaap.NOT_RICH_ENOUGH:
                Logger().warning(err)
                if PlayerManager().isMapInHavenbag(self.currMapId):
                    Logger().debug(f"Player doesnt have enough kamas to use haven bag to join the dest zaap so it will quit the haven bag.")
                    return self.enterHavenBag(self.travelToDestinationOnFeetWithSaveZaap)
                else:
                    return self.travelToDestinationOnFeetWithSaveZaap()

            elif code == UseZaap.DST_ZAAP_NOT_KNOWN:
                Logger().warning(err)
                return self.travelToDestinationOnFeetWithSaveZaap()

            elif code == UseSkill.UNREACHABLE_IE:
                Logger().warning(f"Unreachable IE position of src zaap, can't use it to reach dst zaap map!")
                iePos: MapPoint = kwargs.get("iePosition")
                cellData = MapDisplayManager().dataMap.cells[iePos.cellId]
                if not PlayedCharacterManager().currentZoneRp != cellData.linkedZoneRP:
                    Logger().warning(f"Unreachable IE position of src zaap because of rp zone restriction!")
                    return self.autoTrip(
                        self.srcZaapMapId,
                        cellData.linkedZoneRP,
                        callback=self.onSrcZaapTrip,
                    )
                return self.finish(code, err)

            else:
                return self.finish(code, err)
        self.onDstZaapReached()

    def onSrcZaapTrip(self, code=1, err=None):
        if err:
            if code == AutoTrip.NO_PATH_FOUND:
                Logger().error(f"No path found to source zaap!")
                return self.travelToDestinationOnFeetWithSaveZaap()
            return self.finish(code, err)
        if not self.currMapId:
            return self.onceMapProcessed(lambda: self.onSrcZaapTrip(code, err))
        Logger().debug(f"Source zaap map reached! => Will use zaap to destination.")
        if self.dstZaapVertex.mapId == self.currMapId:
            Logger().warning(f"Destination zaap is on same map as source zaap!")
            self.travelToDestinationOnFeetWithSaveZaap()
        else:
            zaapIe = Kernel().interactivesFrame.getZaapIe()
            if zaapIe:
                self.useZaap(
                    self.dstZaapVertex.mapId,
                    callback=self.onDstZaap_zaapTrip            
                )
            elif self.canUseHavenBag():
                self.enterHavenBag(self.onInsideHavenbag)
            else:
                Logger().warning(f"Can't use a Zaap or haven bag to reach dest zaap, will travel to it on feet.")
                self.travelToDestinationOnFeetWithSaveZaap()

    @classmethod
    def findTravelInfos(
        cls, dst_vertex: Vertex, src_mapId=None, src_vertex=None, maxLen=float("inf")
    ) -> Tuple[Vertex, int, list[Edge]]:
        if dst_vertex is None:
            None, None, None
        if src_vertex is None:
            if src_mapId == dst_vertex.mapId:
                return dst_vertex, 0, []
            rpZ = 1
            minDist = float("inf")
            final_src_vertex = None
            path = None
            while True:
                src_vertex = WorldGraph().getVertex(src_mapId, rpZ)
                if not src_vertex:
                    break
                path = AStar().search(
                    WorldGraph(), src_vertex, dst_vertex, maxPathLength=min(maxLen, minDist)
                )
                if path is not None:
                    dist = len(path)
                    if dist < minDist:
                        minDist = dist
                        final_src_vertex = src_vertex
                        path = path
                rpZ += 1
        else:
            if src_vertex.mapId == dst_vertex.mapId:
                return src_vertex, 0, []
            path = AStar().search(
                WorldGraph(), src_vertex, dst_vertex, maxPathLength=maxLen
            )
            if path is None:
                return None, None, None
            final_src_vertex = src_vertex
            minDist = len(path)
        return final_src_vertex, minDist, path
