from typing import Tuple

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
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
        self.srcZaapVertex = None
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
        self.dstZaapVertex, self.dstZaapDist = self.findDistFrom(
            self.dstVertex, self.dstZaapMapId
        )
        teleportCostFromCurrToDstMap = 10 * MapTools.distL2Maps(
            self.currMapId, self.dstZaapMapId
        )
        Logger().debug(f"Player basic account: {PlayerManager().isBasicAccount()}")
        Logger().debug(
            f"Teleport cost to dst from curr pos is : {teleportCostFromCurrToDstMap:.2f}, teleport max cost is {maxCost}."
        )
        if PlayerManager().isBasicAccount() or teleportCostFromCurrToDstMap > maxCost: # Here we check if we can't use havenbag to reach dest zaap
            if not self.findSrcZaap():
                return self.goToDestinationOnFeet()
        else:
            self.srcZaapDist = 0
        self.dstVertex, self.distFromTarget = self.findDistFrom(
            PlayedCharacterManager().currVertex, dstMapId
        )
        Logger().debug(
            f"Walking dist = {self.distFromTarget}, walking to src zap + walking to dst from dst Zaap = {self.srcZaapDist + self.dstZaapDist}"
        )
        if self.distFromTarget <= self.srcZaapDist + self.dstZaapDist:
            self.goToDestinationOnFeet()
        elif PlayerManager().isBasicAccount() or teleportCostFromCurrToDstMap > maxCost:
            Logger().debug(f"Auto travelling to src zaap on feet")
            self.autoTrip(
                self.srcZaapVertex.mapId,
                self.srcZaapVertex.zoneId,
                callback=self.onSrcZaapTrip,
            )
        else:
            Logger().debug(f"Auto travelling to src zaap with havenbag")
            self.enterHavenBag(lambda event: self.onSrcZaapTrip(True, None))

    def findSrcZaap(self):
        self.srcZaapVertex, self.srcZaapDist = Localizer.findCloseZaapMapId(
            self.currMapId, self.maxCost, self.dstZaapMapId
        )
        if not self.srcZaapVertex:
            Logger().warning(f"No associated zaap found for map {self.dstMapId}.")
            return False
        Logger().debug(f"Found src zaap at {self.srcZaapDist} maps from current pos.")
        return True

    def enterHavenBag(self, callback):
        self.havenBagListener = self.once(
            KernelEvent.InHavenBag,
            callback,
            timeout=5,
            retryNbr=3,
            retryAction=Kernel().roleplayContextFrame.havenbagEnter,
            ontimeout=lambda l: self.finish(False, "Haven bag enter timedout"),
        )
        Kernel().roleplayContextFrame.havenbagEnter()

    def onServerInfo(self, event, msgId, msgType, textId, msgContent, params):
        if textId == 589088:  # Can't join haven bag from current Map
            if self.havenBagListener:
                self.havenBagListener.delete()
            if not self.srcZaapVertex:
                if not self.findSrcZaap():
                    return self.goToDestinationOnFeet()
            Logger().debug(
                f"Can't use haven bag so will travel to source zaap on feet."
            )
            self.autoTrip(
                self.srcZaapVertex.mapId,
                self.srcZaapVertex.zoneId,
                callback=self.onSrcZaapTrip,
            )
        elif textId == 592304:  # Player is busy
            self.finish(
                self.BOT_BUSY,
                "Player is busy so cant use zaap and walking might raise unexpected errors.",
            )

    def onDstZaapSaved(self, code, err):
        if err:
            return self.finish(code, err)
        self.autotripToDestOnFeet()
    
    def onDstZaapReached(self):
        Logger().debug(f"Reached dest map!")
        if self.withSaveZaap:
            self.saveZaap(self.onDstZaapSaved)
        else:
            self.autotripToDestOnFeet()

    def onDstZaap_feetTrip(self, code, err):
        if err:
            if code == AutoTrip.NO_PATH_FOUND:
                return self.onDstZaapUnreachable()
            return self.finish(code, err)
        self.onDstZaapReached()
            
    def autotripToDstZaapOnFeet(self):
        self.autoTrip(self.dstZaapVertex.mapId, self.dstZaapVertex.zoneId, callback=self.onDstZaap_feetTrip)
    
    def autotripToDestOnFeet(self):
        self.autoTrip(self.dstMapId, self.dstZoneId, callback=self.finish)
        
    def onDstZaapUnreachable(self):
        Logger().warning(
            "No path found to dest zaap will travel to dest map on feet"
        )
        return self.autoTrip(
            self.dstMapId, self.dstZoneId, callback=self.finish
        )
        
    def goToDestinationOnFeet(self):
        if self.withSaveZaap:
            Logger().debug(f"Will trip to dest zaap on feet to save it before travelling to dest on feet")
            self.autotripToDstZaapOnFeet()
        else:
            Logger().debug(f"Will auto trip on feet to dest")
            self.autotripToDestOnFeet()
    
    def onDstZaap_zaapTrip(self, code, err, **kwargs):
        if err:
            if code == UseZaap.NOT_RICH_ENOUGH:
                Logger().warning(err)
                if PlayerManager().isMapInHavenbag(self.currMapId):
                    Logger().debug(f"Player is not rich enough to use  haven bag to join dest zaap so will quit haven bag.")
                    return self.enterHavenBag(self.goToDestinationOnFeet)
                else:
                    return self.goToDestinationOnFeet()

            elif code == UseZaap.DST_ZAAP_NOT_KNOWN:
                Logger().warning(err)
                return self.goToDestinationOnFeet()

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
                return self.goToDestinationOnFeet()
            return self.finish(code, err)
        if not self.currMapId:
            return self.onceMapProcessed(lambda: self.onSrcZaapTrip(code, err))
        Logger().debug(f"Source zaap map reached! => Will use zaap to destination.")
        if self.dstZaapVertex.mapId == self.currMapId:
            Logger().warning(f"Destination zaap is on same map as source zaap!")
            self.goToDestinationOnFeet()
        else:
            self.useZaap(
                self.dstZaapVertex.mapId,
                callback=self.onDstZaap_zaapTrip            
            )

    @classmethod
    def findDistFrom(
        cls, srcV: Vertex, mapId, maxLen=float("inf")
    ) -> Tuple[Vertex, int]:
        if srcV is None:
            None, None
        if mapId == srcV.mapId:
            return srcV, 0
        rpZ = 1
        minDist = float("inf")
        vertex = None
        while True:
            dstV = WorldGraph().getVertex(mapId, rpZ)
            if not dstV:
                break
            path = AStar().search(
                WorldGraph(), srcV, dstV, maxPathLength=min(maxLen, minDist)
            )
            if path is not None:
                dist = len(path)
                if dist < minDist:
                    minDist = dist
                    vertex = dstV
            rpZ += 1
        return vertex, minDist
