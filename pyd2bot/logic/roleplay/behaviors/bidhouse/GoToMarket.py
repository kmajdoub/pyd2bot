from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior

class GoToMarket(AbstractBehavior):
    """Behavior for traveling to nearest marketplace of specified type"""
    
    ERROR_HDV_NOT_FOUND = 7676999
    
    def __init__(self, marketplace_gfx_id: int):
        """
        Initialize market travel behavior
        Args:
            marketplace_gfx_id: GFX ID of target marketplace type
        """
        super().__init__()
        self._logger = Logger()
        self.marketplace_gfx_id = marketplace_gfx_id
        self.hdv_vertex = None
        self.path_to_hdv = None

    def run(self) -> bool:
        """Start travel to marketplace"""
        if not self._validate_marketplace_access():
            return False
            
        if self.hdv_vertex != PlayedCharacterManager().currVertex:
            self.travel_using_zaap(
                self.hdv_vertex.mapId,
                self.hdv_vertex.zoneId,
                callback=self._on_market_map_reached
            )
        else:
            self._on_market_map_reached(None, None)
        return True

    def _validate_marketplace_access(self) -> bool:
        """
        Validate marketplace accessibility and setup paths
        Returns: bool indicating if access is valid
        """
        current_map = PlayedCharacterManager().currentMap.mapId
        if not current_map:
            return self.finish(1, "Couldn't determine player current map!")

        self.path_to_hdv = Localizer.findClosestHintMapByGfx(current_map, self.marketplace_gfx_id)
        
        if self.path_to_hdv is None:
            return self.finish(
                self.ERROR_HDV_NOT_FOUND,
                "No accessible marketplace found"
            )
            
        if len(self.path_to_hdv) == 0:
            self.hdv_vertex = PlayedCharacterManager().currVertex
        else:
            self.hdv_vertex = self.path_to_hdv[-1].dst
            
        return True

    def _on_market_map_reached(self, code: int, error: str) -> None:
        Kernel().marketFrame._market_mapId = PlayedCharacterManager().currVertex.mapId
        self.finish(code, error)