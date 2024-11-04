from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class UseTeleportItem(AbstractBehavior):
    CANT_USE_ITEM_IN_MAP = 478886
    TIME_OUT = 47888999
    MAX_TRIES = 3

    def __init__(self) -> None:
        self.nbr_tries = 0
        super().__init__()

    def run(self, iw: ItemWrapper):
        self.once_map_processed(
            lambda: self.finish(True, None), timeout=20, ontimeout=self.onTimeout
        )
        self.on(KernelEvent.ServerTextInfo, self.onServerInfo)
        Kernel().inventoryManagementFrame.useItem(iw)
        self.onNewMap(True, None)
        
    def onServerInfo(self, event, msgId, msgType, textId, msgContent, params):
        if textId == 4641:
            return self.finish(self.CANT_USE_ITEM_IN_MAP, f"Cant use this teleport item on this map")

    def onTimeout(self, listener: Listener):
        Logger().error("Use item timed out!")
        if self.nbr_tries < self.MAX_TRIES:
            listener.armTimer()
            self.nbr_tries += 1
        else:
            self.finish(self.TIME_OUT, "Use teleport item timedout!")
            
    def onNewMap(self, code, err):
        if err:
            return self.finish(code, err)
    
