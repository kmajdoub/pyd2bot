from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.dofus.datacenter.world.Area import Area
from pydofus2.com.ankamagames.dofus.datacenter.world.Hint import Hint
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior

class GoToMarket(AbstractBehavior):
    """Behavior for traveling to nearest marketplace of specified type"""
    
    ERROR_HDV_NOT_FOUND = 7676999
    
    def __init__(self, marketplace_gfx_id: int, exclude_market_at_maps: list[int]=None, item_level=200):
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
        if exclude_market_at_maps is None:
            exclude_market_at_maps = []
        self.exclude_market_at_maps = exclude_market_at_maps
        self.item_level = item_level

    def run(self) -> bool:
        """Start travel to marketplace"""
        if not self._validate_marketplace_access():
            return False
        
        if self.hdv_vertex != PlayedCharacterManager().currVertex or PlayedCharacterManager().currVertex.mapId in self.exclude_market_at_maps:
            self.travel_using_zaap(
                self.hdv_vertex.mapId,
                self.hdv_vertex.zoneId,
                excludeMaps=self.exclude_market_at_maps,
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

        if self.item_level > 60:
            if PlayerManager().isBasicAccount():
                return self.finish(1, "Basic accounts can't sell higher than lvl 60 items, so no market can satisfy that!")

            for hint in Hint.getHints():
                if int(hint.mapId) not in list(map(int, self.exclude_market_at_maps)):
                    map_sub_area = SubArea.getSubAreaByMapId(hint.mapId)
                    if map_sub_area.areaId in [45, 18]: # exclude ankarnam and astrub markets for items with level higher than 60 !
                        self.exclude_market_at_maps.append(hint.mapId)
                
        self.path_to_hdv = Localizer.findClosestHintMapByGfx(current_map, self.marketplace_gfx_id, excludeMaps=self.exclude_market_at_maps)
        
        if self.path_to_hdv is None:
            return self.finish(
                self.ERROR_HDV_NOT_FOUND,
                "No accessible marketplace found"
            )
        
        Logger().debug(f"Found market {len(self.path_to_hdv)} maps away")
        if len(self.path_to_hdv) == 0:
            self.hdv_vertex = PlayedCharacterManager().currVertex
        else:
            self.hdv_vertex = self.path_to_hdv[-1].dst
            
        return True

    def _on_market_map_reached(self, code: int, error: str) -> None:
        if not error:
            Kernel().marketFrame._market_mapId = PlayedCharacterManager().currVertex.mapId
        self.finish(code, error)