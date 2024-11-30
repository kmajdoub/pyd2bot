from enum import Enum, auto
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.inventory.UseTeleportItem import UseTeleportItem
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntRequestEnum import TreasureHuntRequestEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntTypeEnum import TreasureHuntTypeEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.mapTools import MapTools

class TakeTreasureHuntQuest(AbstractBehavior):
    """Behavior for taking a treasure hunt quest from the ATM."""
    
    # Constants from original code
    TAKE_QUEST_MAPID = 128452097
    TAKE_QUEST_ZONE_ID = 1
    TREASURE_HUNT_ATM_IE_ID = 484993
    TREASURE_HUNT_ATM_SKILLUID = 152643320
    ZAAP_HUNT_MAP = 142087694
    FARM_RESOURCES = False

    
    class errors(Enum):
        UNABLE_TO_TAKE_QUEST = auto()
        UNSUPPORTED_HUNT_TYPE = auto()
        
    def __init__(self):
        super().__init__()
        self.maxCost = 2000  # Default max cost for zaap travel
    
    def run(self):
        """Start the quest-taking process."""
        Logger().debug("Starting process to take treasure hunt quest")
        self.goToHuntAtm()
    
    def goToHuntAtm(self):
        """Navigate to the treasure hunt ATM."""
        Logger().debug("AutoTraveling to treasure hunt ATM")
            
        self.autoTrip(
            self.TAKE_QUEST_MAPID,
            farm_resources_on_way=self.FARM_RESOURCES,
            callback=self.on_take_quest_map_reached
        )
    
    def onTeleportToDistributorNearestZaap(self, code, err):
        """Handle teleport results."""
        if code == UseTeleportItem.errors.CANT_USE_ITEM_IN_MAP:
            self.autoTrip(
                self.TAKE_QUEST_MAPID,
                farm_resources_on_way=self.FARM_RESOURCES,
                callback=self.on_take_quest_map_reached
            )
        else:
            self.autoTrip(
                self.TAKE_QUEST_MAPID,
                self.TAKE_QUEST_ZONE_ID,
                farm_resources_on_way=self.FARM_RESOURCES,
                callback=self.on_take_quest_map_reached
            )
    
    def on_take_quest_map_reached(self, code, err):
        """Handle arrival at the quest-taking location."""
        if err:
            return self.finish(code, err)
            
        Logger().debug("Getting treasure hunt from distributor")
        self.use_skill(
            elementId=self.TREASURE_HUNT_ATM_IE_ID,
            skilluid=self.TREASURE_HUNT_ATM_SKILLUID,
            callback=self._on_treasure_hunt_taken
        )
    
    def _on_treasure_hunt_taken(self, code, err):
        """Handle the result of taking the treasure hunt."""
        if err:
            return self.finish(code, err)
            
        self.once(KernelEvent.TreasureHuntRequestAnswer, self.onTreasureHuntRequestAnswer)
    
    def onTreasureHuntRequestAnswer(self, event, code, err):
        """Process the treasure hunt request response."""
        if code == TreasureHuntRequestEnum.TREASURE_HUNT_OK:
            self.on(KernelEvent.TreasureHuntUpdate, self.onQuestInfos)
        else:
            self.finish(self.errors.UNABLE_TO_TAKE_QUEST, f"Failed to take treasure hunt quest: {err}")
    
    
    def onQuestInfos(self, event, questType: int):
        if questType == TreasureHuntTypeEnum.TREASURE_HUNT_CLASSIC:
            self.finish(0, None)
        else:
            return self.finish(self.errors.UNSUPPORTED_HUNT_TYPE, f"Unsupported treasure hunt type : {questType}")
        
    @property
    def currentMapId(self):
        """Get the current map ID."""
        return PlayedCharacterManager().currentMap.mapId