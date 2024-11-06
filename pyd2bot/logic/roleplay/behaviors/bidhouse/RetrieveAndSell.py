from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bank.RetrieveFromBank import RetrieveFromBank
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

    def __init__(self, item_gids: int, sell_batch_sizes: int, return_to_start: bool = False):
        super().__init__()
        self._logger = Logger()
        self._start_map_id = None
        self._start_zone = None
        self._item_gids = item_gids
        self._sell_batch_sizes = sell_batch_sizes
        self._return_to_start = return_to_start

    def run(self) -> bool:
        # Store starting position
        self._start_map_id = PlayedCharacterManager().currentMap.mapId
        self._start_zone = PlayedCharacterManager().currentZoneRp
        self._start_retrieve_cycle()
        return True

    def _start_retrieve_cycle(self):
        """Start a new cycle of retrieving and selling"""
        self._logger.info(f"Starting new retrieve cycle for item {self._item_gids}")

        self.retrieve_items_from_bank(
            items_gids=self._item_gids,
            items_batch_sizes=self._sell_batch_sizes,
            return_to_start=False,  # Don't return since we'll be selling
            callback=self._on_items_retrieved,
        )

    def _on_items_retrieved(self, code, err, uids=None, quantities=None):
        """Handle completion of item retrieval"""
        if err:
            self.finish(code, f"Error retrieving items: {err}")
            return
        
        if code == RetrieveFromBank.ERROR_CODES.NO_ITEMS_TO_RETRIEVE:
            # No more items in bank - we're done
            self._logger.info("No more items in bank - completing behavior")
            self._on_idle()
            return

        # Start selling what we retrieved
        self.sell_items(items_to_sell=self._item_gids, items_batch_sizes=self._sell_batch_sizes, callback=self._on_items_sold)

    def _on_items_sold(self, code, err):
        """Handle completion of market sale"""
        if err:
            self.finish(code, f"Error selling items: {err}")
            return

        # Check if we still have items in inventory
        if not RetrieveFromBank.get_existing_bank_items(self._item_gids):
            self._logger.info("No more items in bank - completing behavior")
            self._on_idle()
            return 

        self._start_retrieve_cycle()

    def _on_idle(self):
        """Handle completion of the entire behavior"""
        if self._return_to_start:
            self._logger.info("Returning to start position")
            self.travel_using_zaap(
                self._start_map_id, self._start_zone, callback=lambda code, err: self.finish(code, err)
            )
        else:
            self.finish(0)
