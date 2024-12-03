from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.dofus.datacenter.world.Area import Area
from pydofus2.com.ankamagames.dofus.datacenter.world.Hint import Hint
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior


class GoToMarket(AbstractBehavior):
    """Behavior for traveling to nearest marketplace of specified type"""

    ERROR_HDV_NOT_FOUND = 7676999

    def __init__(self, marketplace_gfx_id: int, exclude_market_at_maps: list[int] = None, item_level=200):
        """
        Initialize market travel behavior
        Args:
            marketplace_gfx_id: GFX ID of target marketplace type
        """
        super().__init__()
        self._logger = Logger()
        self.marketplace_gfx_id = marketplace_gfx_id
        self.hdv_vertex = None
        self.path_to_market = None
        if exclude_market_at_maps is None:
            exclude_market_at_maps = []
        self.exclude_market_at_maps = exclude_market_at_maps
        self.item_level = item_level

    def run(self) -> bool:
        """Start travel to marketplace"""
        self._search_path_to_market()
        
    def _on_market_search_result(self, code, error, path):
        if path is None or error:
            return self.finish(self.ERROR_HDV_NOT_FOUND, f"No accessible marketplace found, search ended with result error[{code}] {error}")

        self.path_to_market = path

        if len(path) == 0:
            self.hdv_vertex = PlayedCharacterManager().currVertex

        else:
            self.hdv_vertex = path[-1].dst

        Logger().debug(f"Found market {len(path)} maps away at vertex {self.hdv_vertex}")
        
        if (
            self.hdv_vertex != PlayedCharacterManager().currVertex
            or PlayedCharacterManager().currVertex.mapId in self.exclude_market_at_maps
        ):
            self.autoTrip(
                path=self.path_to_market,
                callback=self._on_market_map_reached,
            )
        else:
            self._on_market_map_reached(None, None)

    def _search_path_to_market(self) -> bool:
        """
        Validate marketplace accessibility and setup paths
        Returns: bool indicating if access is valid
        """
        Logger().debug(f"Looking for market for item level {self.item_level}")
        current_map = PlayedCharacterManager().currentMap.mapId
        if not current_map:
            return self.finish(1, "Couldn't determine player current map!")

        if self.item_level > 60:
            if PlayerManager().isBasicAccount():
                return self.finish(
                    1, 
                    "Basic accounts can't sell higher than lvl 60 items!"
                )

            self.exclude_market_at_maps = list(map(int, self.exclude_market_at_maps))

            for hint in Hint.getHints():
                if int(hint.gfx) != self.marketplace_gfx_id:
                    continue

                if int(hint.mapId) not in self.exclude_market_at_maps:
                    map_sub_area = SubArea.getSubAreaByMapId(hint.mapId)
                    if map_sub_area.areaId in [
                        DataEnum.ANKARNAM_AREA_ID,
                        DataEnum.ASTRUB_AREA_ID,
                    ]:  # exclude ankarnam and astrub markets for items with level higher than 60 !
                        Logger().debug(f"Exclude market at mapId {hint.mapId} because it is in area {map_sub_area.area.name}")
                        self.exclude_market_at_maps.append(int(hint.mapId))

        Localizer.findClosestHintMapByGfxAsync(
            self.marketplace_gfx_id,
            callback=self._on_market_search_result,
            excludeMaps=self.exclude_market_at_maps
        )

    def _on_market_map_reached(self, code: int, error: str) -> None:
        if not error:
            Kernel().marketFrame._market_mapId = PlayedCharacterManager().currVertex.mapId
            Kernel().marketFrame._market_gfx = self.marketplace_gfx_id
        self.finish(code, error)
