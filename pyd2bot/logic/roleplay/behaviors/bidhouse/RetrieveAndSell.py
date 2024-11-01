from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bank.RetrieveFromBank import RetrieveFromBank
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class RetrieveAndSell(AbstractBehavior):
    """
    Behavior that continuously retrieves items from bank and sells them on the market
    until bank is depleted of the specified item.
    """

    ERROR_NO_ITEMS = 87656454
    ERROR_BANK_ACCESS = 89987
    ERROR_MARKET_ACCESS = 89988

    def __init__(self, item_gid: int, sell_batch_size: int, return_to_start: bool = False):
        super().__init__()
        self._logger = Logger()
        self._start_map_id = None
        self._start_zone = None
        self._item_gid = item_gid
        self._sell_batch_size = sell_batch_size
        self._return_to_start = return_to_start

    def run(self) -> bool:
        """
        Start the retrieve and sell cycle.

        Args:
            item_gid: GID of item to retrieve and sell
            sell_batch_size: How many items to sell in each market listing
            return_to_start: Whether to return to starting position after completion
            bank_infos: Optional bank location info
        """
        # Store starting position
        self._start_map_id = PlayedCharacterManager().currentMap.mapId
        self._start_zone = PlayedCharacterManager().currentZoneRp
        self._start_retrieve_cycle()
        return True

    def _start_retrieve_cycle(self):
        """Start a new cycle of retrieving and selling"""
        self._logger.info(f"Starting new retrieve cycle for item {self._item_gid}")

        # Retrieve maximum quantity of the item
        self.retrieveFromBank(
            items_gids=[self._item_gid],
            get_max_quantities=True,
            return_to_start=False,  # Don't return since we'll be selling
            callback=self._on_items_retrieved,
        )

    def _on_items_retrieved(self, code, err):
        """Handle completion of item retrieval"""
        if err:
            if code == RetrieveFromBank.ITEM_NOT_FOUND:
                # No more items in bank - we're done
                self._logger.info("No more items in bank - completing behavior")
                self._complete_behavior()
            else:
                # Other error occurred
                self.finish(code, f"Error retrieving items: {err}")
            return

        # Check how many items we got
        item = InventoryManager().inventory.getFirstItemByGID(self._item_gid)
        if not item:
            self._logger.warning("Retrieved items but can't find them in inventory")
            self.finish(self.ERROR_NO_ITEMS, "Retrieved items not found in inventory")
            return

        self._logger.info(f"Retrieved {item.quantity} items, starting market sale")

        # Start selling what we retrieved
        self.sellFromBag(object_gid=self._item_gid, quantity=self._sell_batch_size, callback=self._on_items_sold)

    def _on_items_sold(self, code, err):
        """Handle completion of market sale"""
        if err:
            self.finish(code, f"Error selling items: {err}")
            return

        # Check if we still have items in inventory
        item = InventoryManager().inventory.getFirstItemByGID(self._item_gid)
        if item and item.quantity >= self._sell_batch_size:
            self.finish(code, f"Sell items from bag terminated without critical errors but still have more to sell!")
        else:
            # Inventory depleted - start new retrieve cycle
            self._logger.info("Inventory depleted, starting new retrieve cycle")
            self._start_retrieve_cycle()

    def _complete_behavior(self):
        """Handle completion of the entire behavior"""
        if self._return_to_start:
            self._logger.info("Returning to start position")
            self.travelUsingZaap(
                self._start_map_id, self._start_zone, callback=lambda code, err: self.finish(code, err)
            )
        else:
            self.finish(0)
