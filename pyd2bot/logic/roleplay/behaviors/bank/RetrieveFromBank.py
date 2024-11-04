from typing import List
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class RetrieveFromBank(AbstractBehavior):
    BANK_CLOSE_TIMEOUT = 89987
    RETRIEVE_ITEMS_TIMEOUT = 998877
    ITEM_NOT_FOUND = 87656454
    
    def __init__(self):
        super().__init__()
        self._logger = Logger()
        self._start_map_id = None
        self._start_zone = None
        self._return_to_start = False

    def run(self, item_gids: List[int], get_max_quantities: bool = True, quantities=None, return_to_start=False, bank_infos=None) -> bool:
        self._item_gids = item_gids
        self.items = list["ItemWrapper"]()

        self._get_max = get_max_quantities
        self._return_to_start = return_to_start
        self._quantities = quantities
        
        # Store starting position
        self._start_map_id = PlayedCharacterManager().currentMap.mapId
        self._start_zone = PlayedCharacterManager().currentZoneRp
        
        # Get bank location if not provided
        self.path_to_bank, self.bank_infos = bank_infos or Localizer.findClosestBank()
        self._logger.debug(f"Bank infos: {self.bank_infos.__dict__}")
        
        # Start bank opening sequence
        self.openBank(self.bank_infos, callback=self._on_storage_open)
        return True

    def _on_storage_open(self, code, err):
        if err:
            return self.finish(code, err)
        for gid in self._item_gids:
            item = InventoryManager().bankInventory.getFirstItemByGID(gid)
            if not item:
                self.finish(self.ITEM_NOT_FOUND, f"Item with gid {gid} not found in the bank storage!")
            self.items.append(item)
        self._items_uids = [item.objectUID for item in self.items]
        self._retrieve_items()
    
    def _retrieve_items(self):
        """Send item retrieval request"""
        self.once(
            KernelEvent.InventoryWeightUpdate, 
            self._on_inventory_weight_changed
        )
        if self._get_max:
            self._logger.debug(f"Retrieving all available quantities for items: {self._items_uids}")
            # Transfer all available quantities of these specific items
            Kernel().exchangeManagementFrame.exchangeObjectTransferListToInv(self._items_uids)
        else:
            # Original specific quantity behavior
            if not hasattr(self, '_quantities'):
                raise ValueError("Quantities must be set when not using get_max_quantities")
            self._logger.debug(f"Retrieving specific quantities: {list(zip(self._items_uids, self._quantities))}")
            Kernel().exchangeManagementFrame.exchangeObjectTransferListWithQuantityToInv(
                self._items_uids,
                self._quantities
            )

    def _on_inventory_weight_changed(self, event, last_weight, new_weight, max):
        Logger().info(f"Inventory weight percent changed to : {round(100 * new_weight / max, 1)}%")
        self.once(
            event_id=KernelEvent.ExchangeClose, 
            callback=self._on_storage_closed,
        )
        Kernel().commonExchangeManagementFrame.leaveShopStock()
    
    def _on_storage_closed(self, event, success):
        Logger().info("Bank storage closed")
        if self._return_to_start:
            Logger().info(f"Returning to start point")
            self.travel_using_zaap(self._start_map_id, self._start_zone, callback=self.finish)
        else:
            self.finish(0)

    def with_quantities(self, quantities: List[int]) -> 'RetrieveFromBank':
        """Set specific quantities for the items"""
        if len(quantities) != len(self._item_ids):
            raise ValueError("Must provide same number of quantities as items")
        self._quantities = quantities
        self._get_max = False
        return self