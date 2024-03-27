from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    pass


class EnterHavenBag(AbstractBehavior):
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
        if textId == 589049:  # need to be level 10 to enter haven bag
            self.finish(self.NEED_LVL_10, text)
        elif textId == 589088:  # Can't join haven bag from current Map
            self.finish(self.CANT_USE_IN_CURRENT_MAP, text)

    def useEnterHavenBagShortcut(self):
        if not Kernel().roleplayContextFrame:
            return self.onceFramePushed('RoleplayContextFrame', self.useEnterHavenBagShortcut)
        HaapiEventsManager().registerShortcutUse("openHavenbag")
        Kernel().worker.terminated.wait(0.5)
        Kernel().roleplayContextFrame.havenbagEnter()
        
    def run(self) -> bool:
        if PlayedCharacterManager().infos.level < 10:
            return self.finish(self.NEED_LVL_10, "Need to be level 10 to enter haven bag")
        elif PlayerManager().isMapInHavenbag(PlayedCharacterManager().currentMap.mapId):
            return self.finish(self.ALREADY_IN, "Already in haven bag")
        elif PlayerManager().isBasicAccount():
            return self.finish(self.ONLY_SUBSCRIBED, "Only subscribed accounts can enter haven bag")
        
        self.havenBagListener = self.once(
            KernelEvent.InHavenBag,
            self.finish,
            timeout=self.TIMEOUT,
            retryNbr=self.MAX_RETRIES,
            retryAction=self.onHeavenBagEnterTimeout,
            ontimeout=lambda _: self.finish(self.TIMEDOUT, "Haven bag enter timedout too many times"),
        )
    
        self.on(KernelEvent.ServerTextInfo, self.onServerTextInfo)
        self.useEnterHavenBagShortcut()
