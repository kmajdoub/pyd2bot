from enum import Enum, auto
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class UseTeleportItem(AbstractBehavior):
    MAX_TRIES = 3

    class errors(Enum):
        CANT_USE_ITEM_IN_MAP = auto()
        ALREADY_AT_DESTINATION = auto()
        TIME_OUT = auto()

    def __init__(self) -> None:
        self.nbr_tries = 0
        super().__init__()

    def run(self, iw: ItemWrapper):
        self.once_map_rendered(
            lambda *_: self.finish(0),
            timeout=20, 
            ontimeout=self.onTimeout
        )
        self.on(KernelEvent.ServerTextInfo, self.onServerInfo)
        if not Kernel().inventoryManagementFrame.useItem(iw):
            return self.finish(1, "Couldn't send use teleport item request")
        
    def onServerInfo(self, event, msgId, msgType, textId, msgContent, params):
        if textId == 4641:
            self.finish(self.errors.CANT_USE_ITEM_IN_MAP, f"Cant use this teleport item on this map")
        elif textId == 781094:
            self.finish(self.errors.ALREADY_AT_DESTINATION, f"Already at destination map!")

    def onTimeout(self, listener: Listener):
        Logger().error("Use item timed out!")
        if self.nbr_tries < self.MAX_TRIES:
            listener.armTimer()
            self.nbr_tries += 1
        else:
            self.finish(self.errors.TIME_OUT, "Use teleport item timedout!")

    
