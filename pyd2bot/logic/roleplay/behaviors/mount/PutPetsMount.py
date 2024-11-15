from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.network.enums.CharacterInventoryPositionEnum import CharacterInventoryPositionEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ObjectSetPositionMessage import ObjectSetPositionMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class PutPetsMount(AbstractBehavior):
    
    def __init__(self) -> None:
        super().__init__()
    
    def run(self):
        pet_mounts_available_in_inventory = self.has_items()
        if not pet_mounts_available_in_inventory:
            Logger().debug('Has no pet mounts in inventory')
            return self.finish(0)
        self.sendPetsMountPut(pet_mounts_available_in_inventory[0])
        BenchmarkTimer(2, lambda: self.finish(0)).start()

    @classmethod
    def has_items(cls):
        inventory_items = InventoryManager().inventory.getView("storageEquipment").content
        return [item for item in inventory_items if item is not None and item.typeId == DataEnum.ITEM_TYPE_PETSMOUNT]
    
    def sendPetsMountPut(self, mount_iw: ItemWrapper):
        msg = ObjectSetPositionMessage()
        msg.init(mount_iw.objectUID, CharacterInventoryPositionEnum.ACCESSORY_POSITION_PETS, 1)
        ConnectionsHandler().send(msg)
