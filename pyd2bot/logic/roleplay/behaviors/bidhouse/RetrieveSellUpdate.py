from typing import Dict
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bank.RetrieveFromBank import RetrieveFromBank
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class RetrieveSellUpdate(AbstractBehavior):
    """
    Behavior that continuously retrieves items from bank and sells them on the market
    until bank is depleted of the specified item.
    """

    ERROR_NO_ITEMS = 87656454
    ERROR_BANK_ACCESS = 89987
    ERROR_MARKET_ACCESS = 89988

    def __init__(self, gid_batch_size: Dict[int, int] = None, type_batch_size: Dict[int, int] = None):
        super().__init__()
        self._logger = Logger()
        self._start_map_id = None
        self._start_zone = None
        self.gid_batch_size = gid_batch_size
        self.type_batch_size = type_batch_size
        self.has_remaining = False

    def run(self) -> bool:
        # Store starting position
        self._start_map_id = PlayedCharacterManager().currentMap.mapId
        self._start_zone = PlayedCharacterManager().currentZoneRp
        self._start_retrieve_cycle()
        return True

    def _start_retrieve_cycle(self):
        """Start a new cycle of retrieving and selling"""
        self._logger.info(f"Starting new retrieve cycle for item")

        self.retrieve_items_from_bank(
            type_batch_size=self.type_batch_size,
            gid_batch_size=self.gid_batch_size,
            return_to_start=False,  # Don't return since we'll be selling
            callback=self._on_items_retrieved,
        )

    def _on_items_retrieved(self, code, err, has_remaining=None):
        """Handle completion of item retrieval"""
        if err:
            self.finish(code, f"Error retrieving items: {err}")
            return

        if code == RetrieveFromBank.ERROR_CODES.NO_ITEMS_TO_RETRIEVE:
            # No more items in bank - we're done
            self._logger.info("No more items in bank - completing behavior")
            self._on_idle()
            return

        self.has_remaining = has_remaining

        # Start selling what we retrieved
        self.sell_items(
            gid_batch_size=self.gid_batch_size,
            type_batch_size=self.type_batch_size,
            callback=self._on_items_sold,
        )

    def _on_items_sold(self, code, err):
        """Handle completion of market sale"""
        if err:
            self.finish(code, f"Error selling items: {err}")
            return

        # Check if we still have items in inventory
        if not self.has_remaining:
            self._logger.info("No more items in bank - completing behavior")
            self._on_idle()
            return

        self._start_retrieve_cycle()

    def _on_idle(self):
        """Handle completion of the entire behavior"""
        self.finish(0)
