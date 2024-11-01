from typing import Optional
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import \
    InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.actions.DeleteObjectAction import \
    DeleteObjectAction


class InventoryAPI:

    @classmethod
    def getWeightPercent(cls):
        pourcentt = round(
            (PlayedCharacterManager().inventoryWeight / PlayedCharacterManager().inventoryWeightMax) * 100,
            2,
        )
        return pourcentt

    @classmethod
    def destroyAllItems(cls):
        for iw in InventoryManager().realInventory:
            if not iw.isEquipment:
                doa = DeleteObjectAction.create(iw.objectUID, iw.quantity)
                Kernel().worker.process(doa)

    @classmethod
    def getItemFromInventoryByGID(self, object_gid: int) -> Optional[ItemWrapper]:
        """Get item wrapper from inventory by GID"""
        if object_gid in ItemWrapper._cacheGId:
            return ItemWrapper._cacheGId[object_gid]
            
        inventory = InventoryManager().inventory.getView("real").content
        for item in inventory:
            if item.objectGID == object_gid:
                return item
                
        return None

    @classmethod
    def getItemFromBankByGID(self, object_gid: int) -> Optional[ItemWrapper]:
        """Get item wrapper from inventory by GID"""
        if object_gid in ItemWrapper._cacheGId:
            return ItemWrapper._cacheGId[object_gid]
            
        inventory = InventoryManager().bankInventory.getView("bank").content
        for item in inventory:
            if item.objectGID == object_gid:
                return item
                
        return None