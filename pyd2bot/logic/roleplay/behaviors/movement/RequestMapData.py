from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.common.basic.BasicPingMessage import \
    BasicPingMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapInformationsRequestMessage import \
    MapInformationsRequestMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class RequestMapData(AbstractBehavior):
    REQUEST_MAPDATA_TIMEOUT = 5
    TIMEOUT_MAX_COUNT = 3
    TIMEOUT = 309
    CURRENT_MAP_NOT_FOUND = 304

    def __init__(self) -> None:
        self.mapDataRequestNbrFail = 0
        self.listener = None
        super().__init__()

    def run(self, mapId=None) -> bool:
        if not MapDisplayManager().currentMapPoint:
            return self.finish(self.CURRENT_MAP_NOT_FOUND, "Current Map point is None!")
        if not mapId:
            mapId = MapDisplayManager().currentMapPoint.mapId
        mapId = float(mapId)
        self.mapId = mapId
        Logger().info(f"Requesting data for map {mapId}")
        self.listener = self.onceMapProcessed(
            lambda: self.finish(True, None), 
            mapId=mapId,
            timeout=self.REQUEST_MAPDATA_TIMEOUT,
            ontimeout=self.onMapDataRequestTimeout, 
        )
        self.sendRequest()

    def onMapDataRequestTimeout(self, listener: Listener):
        if PlayedCharacterManager().isFighting:
            return
        Logger().warning("Map data request timeout")
        pingMsg = BasicPingMessage()
        pingMsg.init(True)
        ConnectionsHandler().send(pingMsg)
        self.mapDataRequestNbrFail += 1
        if self.mapDataRequestNbrFail > self.TIMEOUT_MAX_COUNT:
            listener.delete()
            return self.finish(self.TIMEOUT, "Map data request timeout")
        listener.armTimer()
        self.sendRequest()
        
    def sendRequest(self) -> None:
        mirmsg = MapInformationsRequestMessage()
        mirmsg.init(self.mapId)
        ConnectionsHandler().send(mirmsg)