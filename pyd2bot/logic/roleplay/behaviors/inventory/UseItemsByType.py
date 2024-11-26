from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class UseItemsByType(AbstractBehavior):
    
    def __init__(self, item_type: int) -> None:
        super().__init__()
        self.item_type = item_type
        self.item = None

    def run(self):
        self._process_next()
    
    @classmethod
    def has_items(cls, item_type):
        inventory_items = InventoryManager().inventory.getView("storageConsumables").content
        return [item for item in inventory_items if item.typeId == item_type]
        
    def _process_next(self):
        self._items_to_use = self.has_items(self.item_type)
        if not self._items_to_use:
            return self.finish(0)
        
        Logger().debug(f"Found {len(self._items_to_use)} items to use")
        self.item = self._items_to_use.pop()
        self.use_item(self.item, self.item.quantity, self._on_item_used)
    
    def _on_item_used(self, code, error):
        if error:
            Logger().error(f"Error using item {self.item.objectUID}: {error}")
        
        self._process_next()