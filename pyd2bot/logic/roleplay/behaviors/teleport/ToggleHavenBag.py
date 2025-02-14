from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.data.enums import ServerNotificationEnum
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.MapMemoryManager import MapMemoryManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    pass


class ToggleHavenBag(AbstractBehavior):
    NEED_LVL_10 = 589049
    ONLY_SUBSCRIBED = 589048
    TIMEDOUT = 589047
    CANT_USE_IN_CURRENT_MAP = 589088
    ALREADY_IN = 589046
    
    TIMEOUT = 30
    MAX_RETRIES = 3
    
    def __init__(self) -> None:
        super().__init__()

    def onHeavenBagEnterTimeout(self):
        Logger().error("Haven bag enter timedout!")
        self.useEnterHavenBagShortcut()
    
    def onServerTextInfo(self, event, msgId, msgType, textId, text, params):
        if textId == ServerNotificationEnum.DOESNT_HAVE_LVL_FOR_HAVEN_BAG:
            self.finish(self.NEED_LVL_10, text)
        elif textId == ServerNotificationEnum.CANT_USE_HAVEN_BAG_FROM_CURRMAP:
            MapMemoryManager().register_havenbag_allowance(PlayedCharacterManager().currentMap.mapId, False)
            mp = PlayedCharacterManager().currMapPos
            Logger().debug(f"allowTpFrom: {mp.allowTeleportFrom}, allowTpEveryWhere: {mp.allowTeleportEverywhere}, allowTpTo: {mp.allowTeleportTo}")
            self.finish(self.CANT_USE_IN_CURRENT_MAP, text)

    def useEnterHavenBagShortcut(self):
        if not Kernel().roleplayContextFrame:
            return self.once_frame_pushed('RoleplayContextFrame', self.useEnterHavenBagShortcut)
        HaapiEventsManager().registerShortcutUse("openHavenbag")
        Kernel().worker.terminated.wait(0.5)
        Kernel().roleplayContextFrame.havenbagEnter()
        
    def run(self, wanted_state=None) -> bool:
        if PlayedCharacterManager().infos.level < 10:
            return self.finish(self.NEED_LVL_10, "Need to be level 10 to use haven bag")
        if PlayerManager().isBasicAccount():
            return self.finish(self.ONLY_SUBSCRIBED, "Only subscribed accounts can use haven bag")
        if wanted_state is not None:
            player_map_id = PlayedCharacterManager().currentMap.mapId
            if wanted_state:
                if PlayerManager().isMapInHavenbag(player_map_id):
                    return self.finish(self.ALREADY_IN, "Already in havenbag")

                allow_tp = MapMemoryManager().is_havenbag_allowed(player_map_id)
                if allow_tp is not None and not allow_tp:
                    return self.finish(self.CANT_USE_IN_CURRENT_MAP, "Havenbag access from current map is not allowed!")
            
            elif not wanted_state and not PlayerManager().isMapInHavenbag(PlayedCharacterManager().currentMap.mapId):
                return self.finish(self.ALREADY_IN, "Not in haven bag already")
        if wanted_state is not None:
            if wanted_state:
                self.havenBagListener = self.once(
                    KernelEvent.InHavenBag,
                    self.finish,
                    timeout=self.TIMEOUT,
                    retry_nbr=self.MAX_RETRIES,
                    retry_action=self.onHeavenBagEnterTimeout,
                    ontimeout=lambda _: self.finish(self.TIMEDOUT, "Haven bag enter timedout too many times"),
                )
            else:
                self.once_map_rendered(lambda *_: self.finish(0))
        self.on(KernelEvent.ServerTextInfo, self.onServerTextInfo)
        self.useEnterHavenBagShortcut()
