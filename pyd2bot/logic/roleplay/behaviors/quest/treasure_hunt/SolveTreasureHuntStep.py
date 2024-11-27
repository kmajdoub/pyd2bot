from typing import Optional
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.CollectAllMapResources import CollectAllMapResources
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.movement.AutoTripUseZaap import AutoTripUseZaap
from pyd2bot.logic.roleplay.behaviors.quest.treasure_hunt.FindHintNpc import FindHintNpc
from pyd2bot.logic.roleplay.behaviors.quest.treasure_hunt.TreasureHuntPoiDatabase import TreasureHuntPoiDatabase
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.quest.treasureHunt.PointOfInterest import PointOfInterest
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import MapPosition
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.internalDatacenter.quests.TreasureHuntStepWrapper import TreasureHuntStepWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntDigRequestEnum import TreasureHuntDigRequestEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntFlagRequestEnum import TreasureHuntFlagRequestEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntTypeEnum import TreasureHuntTypeEnum
from pydofus2.com.ankamagames.dofus.types.enums.TreasureHuntStepTypeEnum import TreasureHuntStepTypeEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.enums.DirectionsEnum import DirectionsEnum


class SolveTreasureHuntStep(AbstractBehavior):
    """Handles the solving of individual treasure hunt steps."""

    class errors:
        UNSUPPORTED_HUNT_TYPE = 475557
        NO_PATH_TO_STEP = 475558

    RESOURCES_TO_COLLECT_SELL = {
        DataEnum.FISH_TYPE_ID: 100,
        DataEnum.WOOD_TYPE_ID: 100,
        DataEnum.ORES_TYPE_ID: 100,
        DataEnum.PLANTS_TYPE_ID: 100,
        DataEnum.ROSE_OF_SANDS_TYPE_ID: 100,
        DataEnum.MAP_FRAGMENT_TYPE_ID: 1,
    }

    def __init__(
        self,
        current_step: TreasureHuntStepWrapper,
        start_map_id: int,
        max_cost: int,
        farm_resources: bool,
        poi_db: TreasureHuntPoiDatabase,
        submitted_flags: list[int],
        quest_type: int,
    ):
        super().__init__()
        self.current_step = current_step
        self.start_map_id = start_map_id
        self.max_cost = max_cost
        self.farm_resources = farm_resources
        self.poi_db = poi_db
        self.submitted_flags = submitted_flags
        self.quest_type = quest_type
        self.guess_mode = False
        self.guessed_answers = []
        self.current_map_destination = None
        self._is_digging = False

    @property
    def currentMapId(self):
        """Get current map ID."""
        from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import (
            PlayedCharacterManager,
        )

        return PlayedCharacterManager().currentMap.mapId

    def _on_quest_update(self, event, questType: int):
        Logger().info(f"Received quest update : {questType}")
        self.guessMode = False
        if questType == TreasureHuntTypeEnum.TREASURE_HUNT_CLASSIC:
            if not self._is_digging:
                self.finish(0, None, self.guessed_answers)
        else:
            self.finish(self.errors.UNSUPPORTED_HUNT_TYPE, f"Unsupported treasure hunt type : {questType}")

    def run(self):
        """Start solving the current step."""
        self.on_multiple([(KernelEvent.TreasureHuntFlagRequestAnswer, self._on_flag_request_answer, {})])
        self._try_solve()

    def _try_solve_direction_to_poi(self):
        Logger().debug(f"Current step : {self.current_step}")
        excluded_map_ids = set()  # Keep track of unreachable maps

        while True:  # Keep trying until we either find a path or exhaust all possibilities
            next_map_id = self._get_next_hint_map(excluded_map_ids)
            if not next_map_id:
                if self.guess_mode:
                    Logger().error(
                        f"Unable to find any reachable map for poi {self.current_step.poiLabel} in guess mode!"
                    )
                    return self._dig_treasure()
                else:
                    # If normal mode failed, try guess mode
                    Logger().warning("No more maps to try in normal mode, switching to guess mode")
                    self.guess_mode = True
                    excluded_map_ids.clear()  # Clear exclusions for guess mode
                    continue

            dst_vertex, _ = Localizer.findDestVertex(
                PlayedCharacterManager().currVertex,
                next_map_id
            )

            if not dst_vertex:
                Logger().warning(f"Map {next_map_id} is unreachable from current position, excluding it")
                excluded_map_ids.add(next_map_id)
                continue

            # If we get here, we found a reachable map
            Logger().debug(f"Next hint map is {next_map_id}, will travel to it.")
            self.current_map_destination = next_map_id

            self.travel_using_zaap(
                dst_vertex.mapId,
                dst_vertex.zoneId,
                maxCost=self.max_cost,
                farm_resources_on_way=self.farm_resources,
                callback=self._on_next_hint_map_reached,
            )
            return

    def _try_solve(self):
        if self.current_step is None:
            return self._dig_treasure()

        if self.current_step.type == TreasureHuntStepTypeEnum.FIGHT:
            return self._dig_treasure()

        elif self.current_step.type == TreasureHuntStepTypeEnum.DIRECTION_TO_POI:
            return self._try_solve_direction_to_poi()

        elif self.current_step.type == TreasureHuntStepTypeEnum.DIRECTION_TO_HINT:
            FindHintNpc().start(
                self.current_step.count,
                self.current_step.direction,
                callback=self._on_next_hint_map_reached,
                parent=self,
            )

        else:
            return self.finish(
                self.errors.UNSUPPORTED_HUNT_TYPE, f"Unsupported hunt step type {self.current_step.type}"
            )

    def _get_next_hint_map(self, excluded_map_ids: Optional[set] = None) -> Optional[int]:
        """Find the next map to check for the hint."""
        if excluded_map_ids is None:
            excluded_map_ids = set()
            
        map_id = self.start_map_id
        for i in range(20):
            map_id = WorldGraph().nextMapInDirection(map_id, self.current_step.direction)
            if not map_id:
                return None
            
            if map_id in excluded_map_ids:
                Logger().debug(f"Map {map_id} was previously found unreachable, skipping")
                continue

            Logger().debug(f"iter {i + 1}: nextMapId {map_id}.")

            if map_id in self.submitted_flags:
                Logger().debug(f"Map {map_id} has already been submitted for a previous step!")
                continue

            if self.current_step.type == TreasureHuntStepTypeEnum.DIRECTION_TO_POI:
                if (self.start_map_id, self.current_step.poiLabel, map_id) in self.poi_db.wrong_answers:
                    Logger().debug(f"Map {map_id} has already been registred as a wrong answer for this poi")
                    continue

                if not self.guess_mode:
                    if self.poi_db.is_poi_in_map(map_id, self.current_step.poiLabel):
                        poi = PointOfInterest.getPointOfInterestById(self.current_step.poiLabel)
                        Logger().debug(
                            f"Found {poi.name} in Map {map_id} at {i + 1} maps to the {DirectionsEnum(self.current_step.direction)}"
                        )
                        return map_id
                else:
                    Logger().debug(f"Guess mode enabled, will try to find the poi in this map {map_id}")
                    return map_id

        return None

    def _dig_treasure(self):
        """Request to dig for treasure."""
        self._is_digging = True
        self.once(KernelEvent.TreasureHuntDigAnswer, self._on_dig_answer)
        Kernel().questFrame.treasureHuntDigRequest(self.quest_type)

    def _put_flag(self):
        """Place a flag at the current location."""
        self.once(KernelEvent.TreasureHuntUpdate, self._on_quest_update)
        Kernel().questFrame.treasureHuntFlagRequest(self.quest_type, self.current_step.index)

    def _on_selling_over(self, code, err):
        """Handle completion of retrieve/sell workflow."""
        if err:
            return self.finish(code, err)

        Logger().info("Selling complete, resuming travel to hint map...")
        self._travel_to_current_target_hint_map()

    def _on_resurrection_over(self, code, err):
        if err:
            return self.finish(code, err)

        Logger().info("Resurrection complete, resuming travel to hint map...")

        self._travel_to_current_target_hint_map()
    
    def _travel_to_current_target_hint_map(self):
        dst_vertex, _ = Localizer.findDestVertex(
            PlayedCharacterManager().currVertex, self.current_map_destination
        )
        if not dst_vertex:
            Logger().warning("Can't reach hint map from current position, will trigger autotrip to hint map before")
            
        self.travel_using_zaap(
            dst_vertex.mapId,
            dst_vertex.zoneId,
            maxCost=self.max_cost,
            farm_resources_on_way=self.farm_resources,
            callback=self._on_next_hint_map_reached,
        )

    def _on_next_hint_map_reached(self, code, error):
        if error:
            Logger().error(error)
            if code == AutoTrip.NO_PATH_FOUND:
                if self.use_rappel_potion(
                    lambda *_: self._travel_to_current_target_hint_map()
                ):
                    return
                Logger().error("Bot is stuck and has no rappel potion!")

            if code in [FindHintNpc.UNABLE_TO_FIND_HINT, AutoTripUseZaap.NO_PATH_TO_DEST]:
                Logger().warning(error)
                return self._dig_treasure()

            if code == CollectAllMapResources.errors.FULL_PODS:
                Logger().warning(
                    f"Inventory is almost full => will trigger retrieve sell and update items workflow ..."
                )
                # After unload and selling workflow we should again restart hint map traveling
                return self.retrieve_sell(
                    self.RESOURCES_TO_COLLECT_SELL,
                    items_gid_to_keep=[DataEnum.RAPPEL_POTION_GUID],
                    callback=self._on_selling_over,
                )

            if code == CollectAllMapResources.errors.MAP_CHANGED:
                Logger().warning(f"Map changed during resource collection, retrying travel to hint map...")
                return self._travel_to_current_target_hint_map()

            if code == CollectAllMapResources.errors.PLAYER_DEAD:
                Logger().warning(f"Player died while farming resources, will resurrect and retry...")
                return self.auto_resurrect(callback=self._on_resurrection_over)

            return self.finish(code, error)

        if self.guess_mode:
            self.guessed_answers.append((self.start_map_id, self.current_step.poiLabel, self.currentMapId))

        self._put_flag()

    def _on_wrong_answer(self, answer):
        Logger().debug(f"Wrong answer : {answer}")
        if self.guess_mode and answer in self.guessed_answers:
            self.guessed_answers.remove(answer)
        self.poi_db.add_wrong_answer(answer)
        self._try_solve()

    def _on_flag_request_answer(self, event, result_code, err):
        Logger().debug(f"Received flag request answer result : result_code {result_code}, error {err}")

        if result_code == TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_OK:
            return self.finish(0, None, self.guessed_answers)

        answer = (self.start_map_id, self.current_step.poiLabel, self.currentMapId)
        if result_code in [
            TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_WRONG,
            TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_SAME_MAP,
        ]:
            self._on_wrong_answer(answer)
        else:
            self.finish(result_code, f"Flag request error: {err}")

    def _on_dig_answer(self, event, wrongFlagCount, result_code, treasureHuntDigAnswerText):
        """Handle dig responses."""
        self._is_digging = False
        if result_code == TreasureHuntDigRequestEnum.TREASURE_HUNT_DIG_WRONG_AND_YOU_KNOW_IT:
            self.finish(result_code, f"Treasure hunt dig failed: {treasureHuntDigAnswerText}")
        else:
            self.finish(0, None, self.guessed_answers)
