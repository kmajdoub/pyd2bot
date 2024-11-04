from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    pass


class GetOutOfAnkarnam(AbstractBehavior):
    ASTRUB_MAPLOAD_TIMEOUT = 20203
    npcId = -20001
    npcMapId = 153880835
    openGoToAstrubActionId = 3
    hesitateReplayId = 36979
    goToAstrubReplyId = 36977
    ankarnamAreaId = 45
    astrubLandingMapId = 192416776

    def __init__(self) -> None:
        super().__init__()

    def onAstrubMapProcessed(self, event=None):
        self.finish(0, None)

    def onAstrubMapLoadTimeout(self, listener: Listener):
        return self.finish(self.ASTRUB_MAPLOAD_TIMEOUT, f"Load Astrub map '{self.astrubLandingMapId}' timedout!")

    def onGetOutOfIncarnamNpcEnd(self, code, error):
        if error:
            return self.finish(code, error)
        self.once_map_processed(
            callback=self.onAstrubMapProcessed,
            mapId=self.astrubLandingMapId,
            timeout=20,
            ontimeout=self.onAstrubMapLoadTimeout
        )

    def run(self) -> bool:
        sa = SubArea.getSubAreaByMapId(PlayedCharacterManager().currentMap.mapId)
        areaId = sa._area.id
        if areaId != self.ankarnamAreaId:
            Logger().debug(f"GetOutOfAnkarnam: Current area is not Ankarnam! (areaId: {areaId})")
            return self.finish(True, None)
        self.npcDialog(
            self.npcMapId,
            self.npcId,
            self.openGoToAstrubActionId,
            {
                30637: self.hesitateReplayId, 
                30638: self.goToAstrubReplyId,
            },
            callback=self.onGetOutOfIncarnamNpcEnd,
        )
