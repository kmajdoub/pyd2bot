from enum import Enum
import os
import random
import threading

from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.CollectAllMapResources import CollectAllMapResources
from pyd2bot.logic.roleplay.behaviors.mount.PutPetsMount import PutPetsMount
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.inventory.UseItemsByType import UseItemsByType
from pyd2bot.logic.roleplay.behaviors.quest.treasure_hunt.SolveTreasureHuntStep import SolveTreasureHuntStep
from pyd2bot.logic.roleplay.behaviors.quest.treasure_hunt.TreasureHuntPoiDatabase import TreasureHuntPoiDatabase
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.internalDatacenter.quests.TreasureHuntStepWrapper import TreasureHuntStepWrapper
from pydofus2.com.ankamagames.dofus.internalDatacenter.quests.TreasureHuntWrapper import TreasureHuntWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntDigRequestEnum import TreasureHuntDigRequestEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntFlagRequestEnum import TreasureHuntFlagRequestEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntFlagStateEnum import TreasureHuntFlagStateEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntTypeEnum import TreasureHuntTypeEnum
from pydofus2.com.ankamagames.dofus.types.enums.TreasureHuntStepTypeEnum import TreasureHuntStepTypeEnum
from pydofus2.com.ankamagames.dofus.uiApi.PlayedCharacterApi import PlayedCharacterApi
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
HINTS_FILE = os.path.join(CURR_DIR, "hints.json")
WRONG_ANSWERS_FILE = os.path.join(CURR_DIR, "wrongAnswers.json")


class ClassicTreasureHunt(AbstractBehavior):
    class errors(Enum):
        UNSUPPORTED_HUNT_TYPE = 475557
        STEP_DIDNT_CHANGE = 47555822
        UNSUBSCRIBED = 475558

    RESOURCES_TO_COLLECT_SELL = {
        DataEnum.FISH_TYPE_ID: 100, 
        DataEnum.WOOD_TYPE_ID: 100, 
        DataEnum.ORES_TYPE_ID: 100,
        DataEnum.PLANTS_TYPE_ID: 100,
        DataEnum.ROSE_OF_SANDS_TYPE_ID: 100,
        DataEnum.MAP_FRAGMENT_TYPE_ID: 1
    }
    
    FARM_RESOURCES = False

    _poi_db = TreasureHuntPoiDatabase(HINTS_FILE, WRONG_ANSWERS_FILE)

    def __init__(self) -> None:
        super().__init__()
        self.infos: TreasureHuntWrapper = None
        self.currentStep: TreasureHuntStepWrapper = None
        self.defaultMaxCost = None
        self.guessedAnswers = []
        self._chests_to_open = []
        self._deactivate_riding = False
        self._hunts_done = 0
        self._gained_kamas = 0
        self._stop_sig = threading.Event()

    def stop(self, clear_callback=None):
        self._stop_sig.set()

    @property
    def maxCost(self):
        if not self._hunts_done:
            return self.defaultMaxCost
        average_gain = 2 * self._gained_kamas // self._hunts_done
        return max(average_gain, 0)

    def submitted_flag_maps(self):
        return [
            _.mapId
            for _ in self.infos.stepList
            if _.flagState == TreasureHuntFlagStateEnum.TREASURE_HUNT_FLAG_STATE_UNKNOWN
        ]

    def _get_current_step_index(self):
        i = 1
        while i < len(self.infos.stepList):
            if self.infos.stepList[i].flagState == TreasureHuntFlagStateEnum.TREASURE_HUNT_FLAG_STATE_UNSUBMITTED:
                return i
            i += 1
        return None

    def run(self):
        self.on_multiple(
            [
                (KernelEvent.TreasureHuntFinished, self.onHuntFinished, {}),
                (KernelEvent.ObjectAdded, self.onObjectAdded, {}),
                (KernelEvent.ServerTextInfo, self._on_server_notif, {}),
                (KernelEvent.NonSubscriberPopup, self._on_subscription_limitation, {}),
            ]
        )

        self.defaultMaxCost = min(PlayedCharacterApi.inventoryKamas(), 2000)
        self.infos = Kernel().questFrame.getTreasureHunt(TreasureHuntTypeEnum.TREASURE_HUNT_CLASSIC)
        if self.infos is not None:
            if PlayedCharacterManager().is_dead():
                return self.auto_resurrect(callback=lambda *_: self.solve_next_step())
            self.solve_next_step()
        else:
            if PlayedCharacterManager().is_dead():
                return self.auto_resurrect(callback=lambda *_: self.take_treasure_hunt_quest(callback=self._on_quest_taken))
            if PlayedCharacterManager().isPodsFull():
                return self.retrieve_sell(
                    self.RESOURCES_TO_COLLECT_SELL,
                    items_gid_to_keep=[DataEnum.RAPPEL_POTION_GUID],
                    callback=lambda *_: self.take_treasure_hunt_quest(callback=self._on_quest_taken)
                )
            self.take_treasure_hunt_quest(callback=self._on_quest_taken)

    def _on_subscription_limitation(self, event, mods, text):
        self.finish(self.errors.UNSUBSCRIBED, text)

    def _on_server_notif(self, event, msgId, msgType, textId, msgContent, params):
        if textId == ServerNotificationEnum.KAMAS_GAINED:
            self._gained_kamas += int(params[0])
        elif textId == ServerNotificationEnum.KAMAS_LOST:
            self._gained_kamas -= int(params[0])

    def _on_quest_taken(self, code, err, infos=None):
        if err:
            if code == CollectAllMapResources.errors.FULL_PODS:
                Logger().warning(
                    f"Inventory is almost full => will trigger retrieve sell and update items workflow ..."
                )
                # After unload and selling workflow we should again restart hint map traveling
                return self.retrieve_sell(
                    self.RESOURCES_TO_COLLECT_SELL,
                    items_gid_to_keep=[DataEnum.RAPPEL_POTION_GUID],
                    callback=lambda *_: self.take_treasure_hunt_quest(callback=self._on_quest_taken)
                )

            if code == CollectAllMapResources.errors.MAP_CHANGED:
                Logger().warning(f"Map changed during resource collection, retrying travel to quest map...")
                return self.take_treasure_hunt_quest(callback=self._on_quest_taken)
        
            if code == CollectAllMapResources.errors.PLAYER_DEAD:
                Logger().warning(f"Player died while going to quest map, will resurrect and retry...")
                return self.auto_resurrect(callback=lambda *_: self.take_treasure_hunt_quest(callback=self._on_quest_taken))

            return self.finish(code, err)

        Logger().info("Treasure hunt quest taken")
        self.solve_next_step()

    def onObjectAdded(self, event, iw: ItemWrapper, qty: int):
        Logger().info(f"{iw.name}, gid {iw.objectGID}, uid {iw.objectUID}, {iw.description} x{qty} added to inventory")
        if iw.typeId != DataEnum.CHEST_TYPE_ID:
            averageKamasWon = Kernel().averagePricesFrame.getItemAveragePrice(iw.objectGID) * qty
            Logger().debug(f"Average kamas won: {averageKamasWon}")
            self._gained_kamas += averageKamasWon
            self.send(KernelEvent.ObjectObtainedInFarm, iw.objectGID, qty, averageKamasWon)

    def onHuntFinished(self, event, questType):
        Logger().debug(f"Treasure hunt finished")

        if not Kernel().roleplayContextFrame:
            Logger().debug(f"Waiting for roleplay context to start ...")
            return self.once_map_rendered(lambda: self.onHuntFinished(event, questType))

        if self.guessedAnswers:
            for _, poiId, answerMapId in self.guessedAnswers:
                Logger().debug(f"Will memorize the guessed answers : {self.guessedAnswers}")
                self._poi_db.memorize_hint(answerMapId, poiId)
            self.guessedAnswers.clear()

        self._hunts_done += 1

        if PlayedCharacterManager().is_dead():
            Logger().warning(f"Player is dead in treasure hunt fight!")
            return self.auto_resurrect(callback=lambda *_: self.onHuntFinished(event, questType))

        self.check_usable_boxes()

    def check_usable_boxes(self):
        if UseItemsByType.has_items(DataEnum.CHEST_TYPE_ID):
            Logger().debug("Found some chests to open in inventory")
            self.use_items_of_type(DataEnum.CHEST_TYPE_ID, lambda *_: self.check_usable_boxes())
            return True

        if UseItemsByType.has_items(DataEnum.TREASURE_MAX_FRAG_BOX_TYPE_ID):
            Logger().debug("Found some map fragment boxes to open in inventory")
            self.use_items_of_type(DataEnum.TREASURE_MAX_FRAG_BOX_TYPE_ID, lambda *_: self.check_usable_boxes())
            return True
        
        self.take_treasure_hunt_quest(callback=self._on_quest_taken)
        
    @property
    def currentMapId(self):
        return PlayedCharacterManager().currentMap.mapId

    def onPlayerRidingMount(self, code, err, ignoreSame):
        if err:
            Logger().error(f"Error[{code}] while riding mount: {err}")
            self._deactivate_riding = True

        self.solve_next_step(ignoreSame)

    def _on_resurrection(self, code, error, ignoreSame=False):
        if error:
            return self.send(KernelEvent.ClientShutdown, f"Error while resurrecting player: {error}")

        Logger().debug(f"Bot back on form, can continue treasure hunt")
        self.solve_next_step(ignoreSame)

    def solve_next_step(self, ignoreSame=False):
        Logger().debug("Treasure hunt solve step called")        
        if self._stop_sig.is_set():
            return self.finish(self.STOPPED, None)

        if Kernel().fightContextFrame:
            Logger().debug(f"Waiting for fight to end")
            return self.once(
                KernelEvent.RoleplayStarted, 
                lambda *_: self.once_map_rendered(lambda: self.solve_next_step(ignoreSame))
            )

        if PlayedCharacterManager().is_dead():
            Logger().warning(f"Player is dead.")
            return self.auto_resurrect(callback=lambda code, err: self._on_resurrection(code, err, ignoreSame))

        if not PlayedCharacterManager().isPetsMounting:
            Logger().debug("player is not pet mounting")
            if PutPetsMount.has_items():
                Logger().debug("player has available non equipped pet mounts")
                self.put_pet_mount(callback=lambda *_: self.solve_next_step(ignoreSame))
                return

            if not self._deactivate_riding and PlayedCharacterApi.canRideMount():
                Logger().info(f"Mounting {PlayedCharacterManager().mount.name} ...")
                return self.toggle_ride_mount(
                    wanted_ride_state=True, 
                    callback=lambda e, m: self.onPlayerRidingMount(e, m, ignoreSame)
                )

        if PlayedCharacterManager().isPodsFull():
            return self.retrieve_sell(
                self.RESOURCES_TO_COLLECT_SELL,
                items_gid_to_keep=[DataEnum.RAPPEL_POTION_GUID],
                callback=lambda *_: self.solve_next_step(ignoreSame)
            )
    
        self.infos = Kernel().questFrame.getTreasureHunt(TreasureHuntTypeEnum.TREASURE_HUNT_CLASSIC)

        if not self.infos:
            return self.finish("Solve step called but no quest infos found!!")

        lastStep = self.currentStep
        idx = self._get_current_step_index()
        if idx is None:
            self.currentStep = None
        else:
            self.currentStep = self.infos.stepList[idx]
            if not ignoreSame and lastStep == self.currentStep:
                return self.finish(self.errors.STEP_DIDNT_CHANGE, "Step didn't change after update!")
            self.startMapId = self.infos.stepList[idx - 1].mapId

        Logger().debug(f"Infos:\n{self.infos}")
        if self.currentStep is not None:
            if self.currentStep.type != TreasureHuntStepTypeEnum.DIRECTION_TO_POI:
                Logger().debug(f"AutoTraveling to treasure hunt step {idx}, start map {self.startMapId}")
                self.autoTrip(
                    self.startMapId, 
                    callback=self._on_start_map_reached
                )
            else:
                self._on_start_map_reached(0, None)

    def _on_step_solved(self, code, error, guessed_answers=None):
        Logger().debug(f"Solve step finished with result : code {code}, error {error}")

        if guessed_answers:
            self.guessedAnswers.extend(guessed_answers)
                
        if error:
            return self.finish(code, error)

        return self._handle_step_result(code, error)

    def _handle_step_result(self, code, error):
        if code == TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_OK:
            return self.solve_next_step()
            
        elif code in [TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_WRONG,
                    TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_SAME_MAP]:
            return self.solve_next_step(True)
            
        elif code == TreasureHuntDigRequestEnum.TREASURE_HUNT_DIG_WRONG_AND_YOU_KNOW_IT:
            return self.finish(code, error)
            
        elif code == 0:
            self.infos = Kernel().questFrame.getTreasureHunt(TreasureHuntTypeEnum.TREASURE_HUNT_CLASSIC)
            if self.infos:
                return self.solve_next_step()

    def _on_selling_over(self, code, err):
        """Handle completion of retrieve/sell workflow."""
        if err:
            return self.finish(code, err)

        Logger().info("Selling complete, resuming travel to hint map...")
        # Resume travel to hint map
        self.autoTrip(
            self.startMapId, 
            callback=self._on_start_map_reached
        )

    def _on_resurrection_over(self, code, err):
        if err:
            return self.finish(code, err)

        Logger().info("Resurrection complete, resuming travel to hint map...")

        # Resume travel to hint map after resurrection
        self.autoTrip(
            self.startMapId, 
            callback=self._on_start_map_reached
        )


    def _on_start_map_reached(self, code, error):
        if error:
            if code == AutoTrip.NO_PATH_FOUND:
                Logger().warning("No path found to treasure hunt step map!, bot is stuck!")
                KernelEventsManager().send(KernelEvent.ClientShutdown, "Bot is stuck because it cant reach treasure hunt step mapId!")
                return
    
            if code == CollectAllMapResources.errors.FULL_PODS:
                Logger().warning(
                    f"Inventory is almost full => will trigger retrieve sell and update items workflow ..."
                )
                return self.retrieve_sell(
                    self.RESOURCES_TO_COLLECT_SELL,
                    items_gid_to_keep=[DataEnum.RAPPEL_POTION_GUID],
                    callback=self._on_selling_over,
                )

            if code == CollectAllMapResources.errors.MAP_CHANGED:
                Logger().warning(f"Map changed during resource collection, retrying travel to hint map...")
                return self.autoTrip(
                    self.startMapId, 
                    callback=self._on_start_map_reached
                )

            if code == CollectAllMapResources.errors.PLAYER_DEAD:
                Logger().warning(f"Player died while farming resources, will resurrect and retry...")
                return self.auto_resurrect(callback=self._on_resurrection_over)

            return self.finish(code, error)
        
        SolveTreasureHuntStep(
            current_step=self.currentStep,
            start_map_id=self.startMapId,
            max_cost=self.maxCost,
            farm_resources=self.FARM_RESOURCES,
            poi_db=self._poi_db,
            submitted_flags=self.submitted_flag_maps(),
            quest_type=self.infos.questType
        ).start(callback=self._on_step_solved, parent=self)
