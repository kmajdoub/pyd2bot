import json
import os

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.AutoTripUseZaap import AutoTripUseZaap
from pyd2bot.logic.roleplay.behaviors.quest.FindHintNpc import FindHintNpc
from pyd2bot.logic.roleplay.behaviors.teleport.UseTeleportItem import \
    UseTeleportItem
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.datacenter.quest.treasureHunt.PointOfInterest import \
    PointOfInterest
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import \
    MapPosition
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.internalDatacenter.quests.TreasureHuntStepWrapper import \
    TreasureHuntStepWrapper
from pydofus2.com.ankamagames.dofus.internalDatacenter.quests.TreasureHuntWrapper import \
    TreasureHuntWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import \
    PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import \
    InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntDigRequestEnum import TreasureHuntDigRequestEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntFlagRequestEnum import \
    TreasureHuntFlagRequestEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntFlagStateEnum import \
    TreasureHuntFlagStateEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntRequestEnum import \
    TreasureHuntRequestEnum
from pydofus2.com.ankamagames.dofus.network.enums.TreasureHuntTypeEnum import \
    TreasureHuntTypeEnum
from pydofus2.com.ankamagames.dofus.types.enums.TreasureHuntStepTypeEnum import \
    TreasureHuntStepTypeEnum
from pydofus2.com.ankamagames.dofus.uiApi.PlayedCharacterApi import \
    PlayedCharacterApi
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.enums.DirectionsEnum import \
    DirectionsEnum
from pydofus2.mapTools import MapTools

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
HINTS_FILE = os.path.join(CURR_DIR, "hints.json")
WRONG_ANSWERS_FILE = os.path.join(CURR_DIR, "wrongAnswers.json")


class ClassicTreasureHunt(AbstractBehavior):
    UNABLE_TO_FIND_HINT = 475556
    UNSUPPORTED_THUNT_TYPE = 475557
    TAKE_QUEST_MAPID = 128452097
    TREASURE_HUNT_ATM_IEID = 484993
    TREASURE_HUNT_ATM_SKILLUID = 152643320
    RAPPEL_POTION_GUID = 548
    CHESTS_GUID = [15260, 15248, 15261, 15262, 15560, 15270]
    ZAAP_HUNT_MAP = 142087694
    REST_TIME_BETWEEN_HUNTS = 60 * 5
    STEP_DIDNT_CHANGE = 47555822

    with open(HINTS_FILE, "r") as fp:
        hint_db = json.load(fp)

    with open(WRONG_ANSWERS_FILE, "r") as fp:
        json_content = json.load(fp)
        wrongAnswers: set = set([tuple(_) for _ in json_content["recordedWrongAnswers"]])

    @classmethod
    def saveHints(cls):
        with open(HINTS_FILE, "w") as fp:
            json.dump(cls.hint_db, fp, indent=2)

    def __init__(self) -> None:
        super().__init__()
        self.infos: TreasureHuntWrapper = None
        self.currentStep: TreasureHuntStepWrapper = None
        self.maxCost = 800
        self.guessMode = False
        self.guessedAnswers = []
        self._chests_to_open = []
        self._deactivate_riding = False

    def submitet_flag_maps(self):
        return [
            _.mapId
            for _ in self.infos.stepList
            if _.flagState == TreasureHuntFlagStateEnum.TREASURE_HUNT_FLAG_STATE_UNKNOWN
        ]

    def getCurrentStepIndex(self):
        i = 1
        while i < len(self.infos.stepList):
            if self.infos.stepList[i].flagState == TreasureHuntFlagStateEnum.TREASURE_HUNT_FLAG_STATE_UNSUBMITTED:
                return i
            i += 1
        return None

    def run(self):
        self.on(KernelEvent.TreasureHuntUpdate, self.onUpdate)
        self.on(KernelEvent.TreasureHuntFinished, self.onHuntFinished)
        self.on(KernelEvent.ObjectAdded, self.onObjectAdded)
        self.on(KernelEvent.TreasureHuntFlagRequestAnswer, self.onFlagRequestAnswer)
        self.on(KernelEvent.TreasureHuntDigAnswer, self.onDigAnswer)
        self.infos = Kernel().questFrame.getTreasureHunt(TreasureHuntTypeEnum.TREASURE_HUNT_CLASSIC)
        if self.infos is not None:
            return self.solveNextStep()
        self.goToHuntAtm()

    def onDigAnswer(self, event, wrongFlagCount, result, treasureHuntDigAnswerText):
        if result == TreasureHuntDigRequestEnum.TREASURE_HUNT_DIG_WRONG_AND_YOU_KNOW_IT:
            return self.finish(result, f"Treasure hunt dig failed for reason : {treasureHuntDigAnswerText}")

    def onFlagRequestAnswer(self, event, result, err):
        if result == TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_OK:
            pass
        elif result in [TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_WRONG]:
            answer = (self.startMapId, self.currentStep.poiLabel, self.currentMapId)
            Logger().debug(f"Wrong answer : {answer}")
            if answer in self.guessedAnswers:
                self.guessedAnswers.remove(answer)
            self.wrongAnswers.add(answer)
            with open(WRONG_ANSWERS_FILE, "w") as fp:
                json.dump({"recordedWrongAnswers": list(self.wrongAnswers)}, fp)
            self.solveNextStep(True)
        elif result in [
            TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_ERROR_UNDEFINED,
            TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_TOO_MANY,
            TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_ERROR_IMPOSSIBLE,
            TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_WRONG_INDEX,
            TreasureHuntFlagRequestEnum.TREASURE_HUNT_FLAG_SAME_MAP,
        ]:
            KernelEventsManager().send(
                KernelEvent.ClientShutdown, f"Treasure hunt flag request error : {result} {err}"
            )

    def onTelportToDistributorNearestZaap(self, code, err):
        if code == UseTeleportItem.CANT_USE_ITEM_IN_MAP:
            self.autotripUseZaap(
                self.TAKE_QUEST_MAPID, withSaveZaap=True, maxCost=self.maxCost, callback=self.onTakeQuestMapReached
            )
        else:
            self.autoTrip(self.TAKE_QUEST_MAPID, 1, callback=self.onTakeQuestMapReached)

    def goToHuntAtm(self):
        Logger().debug(f"AutoTravelling to treasure hunt ATM")
        distanceToTHATMZaap = MapTools.distanceBetweenTwoMaps(self.currentMapId, self.ZAAP_HUNT_MAP)
        Logger().debug(f"Distance to ATM Zaap is {distanceToTHATMZaap} maps steps")
        if distanceToTHATMZaap > 12:
            if int(Kernel().zaapFrame.spawnMapId) == int(self.ZAAP_HUNT_MAP):
                iw = ItemWrapper._cacheGId.get(self.RAPPEL_POTION_GUID)
                if iw:
                    return UseTeleportItem().start(iw, callback=self.onTelportToDistributorNearestZaap, parent=self)
                for iw in InventoryManager().inventory.getView("storageConsumables").content:
                    if iw.objectGID == self.RAPPEL_POTION_GUID or "rappel" in iw.name.lower():
                        return UseTeleportItem().start(
                            iw, callback=self.onTelportToDistributorNearestZaap, parent=self
                        )
                else:
                    Logger().debug(f"No rappel potions found in player consumable view")
            else:
                Logger().debug(f"Saved Zaap ({Kernel().zaapFrame.spawnMapId}) is not the TH-ATM zaap")
        self.autotripUseZaap(
            self.TAKE_QUEST_MAPID, withSaveZaap=True, maxCost=self.maxCost, callback=self.onTakeQuestMapReached
        )

    def onObjectAdded(self, event, iw: ItemWrapper):
        Logger().info(f"{iw.name}, gid {iw.objectGID}, uid {iw.objectUID}, {iw.description} added to inventory")
        if iw.objectGID in self.CHESTS_GUID:
            self._chests_to_open.append(iw)

    def onHuntFinished(self, event, questType):
        Logger().debug(f"Treasure hunt finished")
        if not Kernel().roleplayContextFrame:
            Logger().debug(f"Waiting for roleplay to start")
            return self.onceMapProcessed(lambda: self.onHuntFinished(event, questType))
        if self.guessedAnswers:
            for _, poiId, answerMapId in self.guessedAnswers:
                Logger().debug(f"Will memorise guessed answers : {self.guessedAnswers}")
                self.memorizeHint(answerMapId, poiId)
            self.guessedAnswers.clear()
            self.guessMode = False
        if self._chests_to_open:
            iw = self._chests_to_open.pop(0)
            HaapiEventsManager().sendInventoryOpenEvent()
            if not Kernel().worker.terminated.wait(3):
                Kernel().inventoryManagementFrame.useItem(iw)
                BenchmarkTimer(3, lambda: self.onHuntFinished(event, questType)).start()
        else:
            Logger().debug(f"Sleeping for 5 minutes before going to the next hunt, to avoid being kicked")
            BenchmarkTimer(self.REST_TIME_BETWEEN_HUNTS, lambda: self.goToHuntAtm()).start()

    def onTakeQuestMapReached(self, code, err):
        if err:
            return self.finish(code, err)
        Logger().debug(f"Getting treasure hunt from distributor")
        self.useSkill(
            elementId=self.TREASURE_HUNT_ATM_IEID,
            skilluid=self.TREASURE_HUNT_ATM_SKILLUID,
            callback=self.onTreasurHuntTaken,
        )

    def onTreasurHuntTaken(self, code, err):
        if err:
            return self.finish(code, err)
        self.once(KernelEvent.TreasureHuntRequestAnswer, self.onTreaSureHuntRequestAnswer)

    def onTreaSureHuntRequestAnswer(self, event, code, err):
        if code == TreasureHuntRequestEnum.TREASURE_HUNT_OK:
            if not self.hasListener(KernelEvent.TreasureHuntUpdate):
                self.on(KernelEvent.TreasureHuntUpdate, self.onUpdate)
        else:
            self.finish(code, err)

    @property
    def currentMapId(self):
        return PlayedCharacterManager().currentMap.mapId

    @classmethod
    def memorizeHint(cls, mapId, poiId):
        mp = MapPosition.getMapPositionById(mapId)
        if str(mp.worldMap) not in cls.hint_db:
            cls.hint_db[str(mp.worldMap)] = {}
        worldHints = cls.hint_db[str(mp.worldMap)]
        if str(mp.id) not in worldHints:
            cls.hint_db[str(mp.worldMap)][str(mp.id)] = []
        cls.hint_db[str(mp.worldMap)][str(mp.id)].append(poiId)
        cls.saveHints()

    @classmethod
    def removePoiFromMap(cls, mapId, poiId):
        mp = MapPosition.getMapPositionById(mapId)
        if str(mp.worldMap) not in cls.hint_db:
            return
        worldHints = cls.hint_db[str(mp.worldMap)]
        if str(mp.id) not in worldHints:
            return
        mapHints = [_ for _ in worldHints[str(mp.id)] if _ != poiId]
        cls.hint_db[str(mp.worldMap)][str(mp.id)] = mapHints
        cls.saveHints()

    @classmethod
    def isPoiInMap(cls, mapId, poiId):
        mp = MapPosition.getMapPositionById(mapId)
        if str(mp.worldMap) not in cls.hint_db:
            return False
        worldHints = cls.hint_db[str(mp.worldMap)]
        if str(mp.id) not in worldHints:
            return False
        mapHints: list = worldHints[str(mp.id)]
        return poiId in mapHints

    def getNextHintMap(self):
        mapId = self.startMapId
        for i in range(10):
            mapId = self.nextMapInDirection(mapId, self.currentStep.direction)
            if not mapId:
                return None
            Logger().debug(f"iter {i + 1}: nextMapId {mapId}.")
            if mapId in self.submitet_flag_maps():
                Logger().debug(f"Map {mapId} has already been submitted for a previous step")
                continue
            if self.currentStep.type == TreasureHuntStepTypeEnum.DIRECTION_TO_POI:
                if (self.startMapId, self.currentStep.poiLabel, mapId) in self.wrongAnswers:
                    Logger().debug(f"Map {mapId} has already been registred as a wrong answer for this poi")
                    continue
                if not self.guessMode:
                    if self.isPoiInMap(mapId, self.currentStep.poiLabel):
                        poi = PointOfInterest.getPointOfInterestById(self.currentStep.poiLabel)
                        Logger().debug(
                            f"Found {poi.name} in Map {mapId} at {i + 1} maps to the {DirectionsEnum(self.currentStep.direction)}"
                        )
                        return mapId
                else:
                    Logger().debug(f"Guess mode enabled, will try to find the poi in this map {mapId}")
                    return mapId
        return None

    @classmethod
    def nextMapInDirection(cls, mapId, direction):
        for vertex in WorldGraph().getVertices(mapId).values():
            for edge in WorldGraph().getOutgoingEdgesFromVertex(vertex):
                for transition in edge.transitions:
                    if transition.direction != -1 and transition.direction == direction:
                        return edge.dst.mapId

    def onPlayerRidingMount(self, code, err, ignoreSame):
        if err:
            Logger().error(f"Error[{code}] while riding mount: {err}")
            self._deactivate_riding = True
        self.solveNextStep(ignoreSame)

    def onRevived(self, code, error, ignoreSame=False):
        if error:
            return KernelEventsManager().send(KernelEvent.ClientShutdown, f"Error while auto-reviving player: {error}")
        Logger().debug(f"Bot back on form, can continue treasure hunt")
        self.solveNextStep(ignoreSame)

    def solveNextStep(self, ignoreSame=False):
        if Kernel().fightContextFrame:
            Logger().debug(f"Waiting for fight to end")
            return self.once(
                KernelEvent.RoleplayStarted, lambda e: self.onceMapProcessed(lambda: self.solveNextStep(ignoreSame))
            )
        if PlayedCharacterManager().isDead():
            Logger().warning(f"Player is dead.")
            return self.autoRevive(callback=lambda code, err: self.onRevived(code, err, ignoreSame))
        if not self._deactivate_riding and PlayedCharacterApi.canRideMount():
            Logger().info(f"Mounting {PlayedCharacterManager().mount.name} ...")
            return self.toggleRideMount(wanted_ride_state=True, callback=lambda e, r: self.onPlayerRidingMount(e, r, ignoreSame))
        lastStep = self.currentStep
        idx = self.getCurrentStepIndex()
        if idx is None:
            self.currentStep = None
        else:
            self.currentStep = self.infos.stepList[idx]
            if not ignoreSame and lastStep == self.currentStep:
                return self.finish(self.STEP_DIDNT_CHANGE, "Step didnt change after update!")
            self.startMapId = self.infos.stepList[idx - 1].mapId
        Logger().debug(f"Infos:\n{self.infos}")
        if self.currentStep is not None:
            if self.currentStep.type != TreasureHuntStepTypeEnum.DIRECTION_TO_POI:
                Logger().debug(f"AutoTravelling to treasure hunt step {idx}, start map {self.startMapId}")
                self.autotripUseZaap(self.startMapId, maxCost=self.maxCost, callback=self.onStartMapReached)
            else:
                self.onStartMapReached(True, None)

    def digTreasure(self):
        Kernel().questFrame.treasureHuntDigRequest(self.infos.questType)

    def puFlag(self):
        Kernel().questFrame.treasureHuntFlagRequest(self.infos.questType, self.currentStep.index)

    def onNextHintMapReached(self, code, err):
        if err:
            if code in [FindHintNpc.UNABLE_TO_FIND_HINT, AutoTripUseZaap.NO_PATH_TO_DEST]:
                Logger().warning(err)
                return self.digTreasure()
            return self.finish(code, err)
        if self.guessMode:
            self.guessedAnswers.append((self.startMapId, self.currentStep.poiLabel, self.currentMapId))
        self.puFlag()

    def onUpdate(self, event, questType: int):
        self.guessMode = False
        if questType == TreasureHuntTypeEnum.TREASURE_HUNT_CLASSIC:
            self.infos = Kernel().questFrame.getTreasureHunt(questType)
            self.solveNextStep()
        else:
            return self.finish(self.UNSUPPORTED_THUNT_TYPE, f"Unsupported treasure hunt type : {questType}")

    def onStartMapReached(self, code, err):
        if err:
            return self.finish(code, err)
        if self.currentStep is None:
            Kernel().questFrame.treasureHuntDigRequest(self.infos.questType)
        elif self.currentStep.type == TreasureHuntStepTypeEnum.FIGHT:
            Kernel().questFrame.treasureHuntDigRequest(self.infos.questType)
        elif self.currentStep.type == TreasureHuntStepTypeEnum.DIRECTION_TO_POI:
            Logger().debug(f"Current step : {self.currentStep}")
            nextMapId = self.getNextHintMap()
            if not nextMapId:
                mp = MapPosition.getMapPositionById(self.startMapId)
                Logger().error(
                    f"Unable to find Map of poi {self.currentStep.poiLabel} from start map {self.startMapId}:({mp.posX}, {mp.posY})!"
                )
                self.guessMode = True
                nextMapId = self.getNextHintMap()
                if not nextMapId:
                    self.guessMode = False
                    Logger().error(
                        f"Unable to find Map of poi {self.currentStep.poiLabel} from start map {self.startMapId} in guess mode!"
                    )
                    return self.digTreasure()
            Logger().debug(f"Next hint map is {nextMapId}, will travel to it.")
            self.autotripUseZaap(nextMapId, maxCost=self.maxCost, callback=self.onNextHintMapReached)
        elif self.currentStep.type == TreasureHuntStepTypeEnum.DIRECTION_TO_HINT:
            FindHintNpc().start(
                self.currentStep.count, self.currentStep.direction, callback=self.onNextHintMapReached, parent=self
            )
        else:
            return self.finish(self.UNSUPPORTED_THUNT_TYPE, f"Unsupported hunt step type {self.currentStep.type}")
