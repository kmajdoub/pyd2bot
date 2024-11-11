from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class UseItem(AbstractBehavior):

    def __init__(self, iw: ItemWrapper, qty: int) -> None:
        super().__init__()
        self.item = iw
        self.qty = qty

    def run(self):
        self.once(KernelEvent.ObjectDeleted, self._on_item_deleted)
        self.once(KernelEvent.ObjectAdded, self._on_item_added)
        HaapiEventsManager().sendInventoryOpenEvent()
        Kernel().inventoryManagementFrame.useItem(self.item, self.qty)
    
    def _on_item_deleted(self, event, item_uid):
        if item_uid == self.item.objectUID:
            self.finish(0)
        else:
            Logger().warning(f"received object deleted event for object other than the one we are consuming!")
    
    def _on_item_added(self, event, item: ItemWrapper, quantity):
        if item.objectGID == self.item.objectGID and quantity < 0:
            if -quantity > self.qty:
                Logger().warning("Lost more than the quantity used!")
            return self.finish(0)
