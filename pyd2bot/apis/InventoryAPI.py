from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import (
    InventoryManager,
)
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import (
    PlayedCharacterManager,
)
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.actions.DeleteObjectAction import (
    DeleteObjectAction,
)

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
