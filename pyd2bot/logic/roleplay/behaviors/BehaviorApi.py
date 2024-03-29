import json
import os
from typing import TYPE_CHECKING

from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import \
    InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
        Edge
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import \
        Transition

__dir__ = os.path.dirname(os.path.abspath(__file__))
SPECIAL_DESTINATIONS_PATH = os.path.join(__dir__, "special_destinations.json")
with open(SPECIAL_DESTINATIONS_PATH, "r") as f:
    SPECIAL_DESTINATIONS = json.load(f)
# Sort the dictionary items by 'pereference' in descending order
SPECIAL_DESTINATIONS = sorted(SPECIAL_DESTINATIONS.items(), key=lambda x: x[1]['pereference'], reverse=True)


class BehaviorApi:
    ANKARNAM_AREAID = 45
    ASTRUB_AREAID = 95
    NEW_VALONIA_AREAID = 93
    SPECIAL_AREA_INFOS_NOT_FOUND_ERROR = 89091
    PLAYER_IN_FIGHT_ERROR = 89090
    CELECTIAL_SUBAREA_ID = 446

    def __init__(self) -> None:
        pass

    def getSpecialDestination(self, srcAreaId, dstAreaId):
        for _, info in SPECIAL_DESTINATIONS:
            if info["exclude_self"] and srcAreaId == dstAreaId:
                continue
            if (info["dstAreaId"] == "*" or dstAreaId in info["dstAreaId"]) and (info["srcAreaId"] == "*" or srcAreaId in info["srcAreaId"]):
                info["replies"] = {int(k): v for k, v in info["replies"].items()}
                Logger().info(f"Special destination matched for srcAreaId={srcAreaId}, dstAreaId={dstAreaId} : {info}")
                return info
        return None

    def autotripUseZaap(self, dstMapId, dstZoneId=None, withSaveZaap=False, maxCost=None, excludeMaps=[], check_special_dest=True, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.AutoTripUseZaap import \
            AutoTripUseZaap
        
        if check_special_dest:
            if self.checkSpecialDestination(dstMapId, dstZoneId, callback=callback):
                return
            
        if not maxCost:
            maxCost = InventoryManager().inventory.kamas * 0.3
            Logger().debug(f"Player max teleport cost is {maxCost}")

        dstsubArea = SubArea.getSubAreaByMapId(dstMapId)
        
        if PlayerManager().isBasicAccount() and not dstsubArea.basicAccountAllowed:
            return callback(0, "Destination map is not allowed for basic accounts!")
            
        if PlayedCharacterManager().currentSubArea.id == self.CELECTIAL_SUBAREA_ID and dstsubArea.id != self.CELECTIAL_SUBAREA_ID:
            Logger().info(f"Player is in celestial dimension, and wants to get out of there.")

            def onOutOfCelestialDim(code, err):
                if err:
                    return callback(code, f"Could not get player out of celestial dimension : {err}")
                self.autotripUseZaap(dstMapId, dstZoneId, withSaveZaap, maxCost, excludeMaps, callback=callback)

            return self.autoTrip(154010883, 1, callback=onOutOfCelestialDim)

        path_to_dest_zaap = Localizer.findPathtoClosestZaap(dstMapId, maxCost, excludeMaps=excludeMaps, onlyKnownZaap=False)
        if not path_to_dest_zaap:
            Logger().warning(f"No dest zaap found for cost {maxCost} and map {dstMapId}!")
            return self.autoTrip(dstMapId, dstZoneId, callback=callback)
        dstZaapVertex = path_to_dest_zaap[-1].dst
        
        if not PlayedCharacterManager().isZaapKnown(dstZaapVertex.mapId):
            Logger().debug(f"Dest zaap at vertex {dstZaapVertex} is not known ==> We need to travel to register it.")

            def onDstZaapTrip(code, err):
                if err:
                    Logger().error(f"Can't reach the dest zaap at {dstZaapVertex} : {err}")
                    return self.autoTrip(dstMapId, dstZoneId, callback=callback)
                if withSaveZaap:
                    def onDstZaapSaved(code, err):
                        if err:
                            return callback(code, err)
                        self.autoTrip(dstMapId, dstZoneId, callback=callback)

                    return self.saveZaap(onDstZaapSaved)
                self.autoTrip(dstMapId, dstZoneId, callback=callback)

            return self.autotripUseZaap(
                dstZaapVertex.mapId,
                dstZaapVertex.zoneId,
                excludeMaps=excludeMaps + [dstZaapVertex.mapId],
                callback=onDstZaapTrip,
            )

        Logger().debug(f"Dst zaap at {dstZaapVertex} is found in known ZAAPS, Autotriping with zaaps to {dstMapId}, zoneId={dstZoneId}")

        def onAutoTripUseZaapEnd(code, err):
            if err and code == AutoTripUseZaap.NO_PATH_TO_DEST:
                Logger().error(err)
                Logger().info("Trying to reach the destination with classic auto trip as last resort.")
                return self.autoTrip(dstMapId, dstZoneId, callback=callback)
            return callback(code, err)

        AutoTripUseZaap().start(
            dstMapId,
            dstZoneId,
            dstZaapVertex.mapId,
            withSaveZaap=withSaveZaap,
            maxCost=maxCost,
            callback=onAutoTripUseZaapEnd,
            parent=self,
        )

    def autoTrip(self, dstMapId, dstZoneId=None, path: list["Edge"] = None, check_special_dest=True, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
        from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
        Logger().info(f"Basic auto trip to map {dstMapId}, rpzone {dstZoneId} called.")
        if Kernel().fightContextFrame:
            Logger().error(f"Player is in Fight => Can't auto trip.")
            return callback(self.PLAYER_IN_FIGHT_ERROR, "Player is in Fight")

        if check_special_dest:
            if self.checkSpecialDestination(dstMapId, dstZoneId, useZaap=False, callback=callback):
                return

        AutoTrip().start(dstMapId, dstZoneId, path, callback=callback, parent=self)
    
    def checkSpecialDestination(self, dstMapId, dstZoneId, useZaap=True, callback=None):
        srcSubArea = SubArea.getSubAreaByMapId(PlayedCharacterManager().currentMap.mapId)
        srcAreaId = srcSubArea.areaId
        dstSubArea = SubArea.getSubAreaByMapId(dstMapId)
        dstAreaId = dstSubArea.areaId

        def onSpecialDestReached(code, err):
            if err:
                return callback(code, f"Could not reach special destination {dstSubArea.name} ({dstMapId}) : {err}")
            if useZaap:
                self.autotripUseZaap(dstMapId, dstZoneId, callback=callback)
            else:
                self.autoTrip(dstMapId, dstZoneId, callback=callback)

        infos = self.getSpecialDestination(srcAreaId, dstAreaId)
        if infos:
            self.goToSpecialDestination(
                infos,
                useZaap=useZaap,
                callback=onSpecialDestReached,
                dstSubAreaName=dstSubArea.name,
            )
            return True
        return False

    def goToSpecialDestination(self, infos, useZaap=True, callback=None, dstSubAreaName=""):
        Logger().info(f"Auto trip to a special destination ({dstSubAreaName}). Using zaap={useZaap}")

        def onNpcDialogEnd(code, err):
            if err:
                return callback(code, err)
            self.onceMapProcessed(
                callback=lambda: callback(True, None),
                mapId=infos["landingMapId"],
            )

        self.npcDialog(
            infos["npcMapId"],
            infos["npcId"],
            infos["openDialiogActionId"],
            infos["replies"],
            useZaap=useZaap,
            callback=onNpcDialogEnd,
        )

    def changeMap(self, transition: "Transition" = None, edge: "Edge" = None, dstMapId=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import \
            ChangeMap

        ChangeMap().start(transition, edge, dstMapId, callback=callback, parent=self)

    def enterHavenBag(self, wanted_state=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.teleport.EnterHavenBag import \
            EnterHavenBag

        EnterHavenBag().start(wanted_state=wanted_state, callback=callback, parent=self)
    
    def toggleRideMount(self, wanted_ride_state=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.mount.ToggleRideMount import ToggleRideMount

        ToggleRideMount().start(wanted_ride_state=wanted_ride_state, callback=callback, parent=self)

    def mapMove(
        self,
        destCell,
        exactDistination=True,
        forMapChange=False,
        mapChangeDirection=-1,
        callback=None,
        cellsblacklist=[],
    ):
        from pyd2bot.logic.roleplay.behaviors.movement.MapMove import MapMove

        MapMove().start(
            destCell,
            exactDistination=exactDistination,
            forMapChange=forMapChange,
            mapChangeDirection=mapChangeDirection,
            callback=callback,
            cellsblacklist=cellsblacklist,
            parent=self,
        )

    def requestMapData(self, mapId=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.RequestMapData import \
            RequestMapData

        RequestMapData().start(mapId, callback=callback, parent=self)

    def autoRevive(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.misc.AutoRevive import AutoRevive

        AutoRevive().start(callback=callback, parent=self)

    def attackMonsters(self, entityId, callback=None):
        from pyd2bot.logic.roleplay.behaviors.fight.AttackMonsters import \
            AttackMonsters

        AttackMonsters().start(entityId, callback=callback, parent=self)

    def farmFights(self, timeout=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.fight.GroupLeaderFarmFights import \
            GroupLeaderFarmFights

        GroupLeaderFarmFights().start(timeout=timeout, callback=callback, parent=self)

    def muleFighter(self, leader, callback=None):
        from pyd2bot.logic.roleplay.behaviors.fight.MuleFighter import \
            MuleFighter

        MuleFighter().start(leader, callback=callback, parent=self)

    def saveZaap(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.teleport.SaveZaap import SaveZaap

        SaveZaap().start(callback=callback, parent=self)

    def useZaap(self, dstMapId, saveZaap=False, callback=None):
        from pyd2bot.logic.roleplay.behaviors.teleport.UseZaap import UseZaap

        UseZaap().start(dstMapId, saveZaap, callback=callback, parent=self)

    def useSkill(
        self,
        ie=None,
        cell=None,
        exactDistination=False,
        waitForSkillUsed=True,
        elementId=None,
        skilluid=None,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill

        UseSkill().start(
            ie, cell, exactDistination, waitForSkillUsed, elementId, skilluid, callback=callback, parent=self
        )

    def soloFarmFights(self, timeout=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.fight.SoloFarmFights import \
            SoloFarmFights

        SoloFarmFights().start(timeout=timeout, callback=callback, parent=self)

    def resourceFarm(self, timeout=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import \
            ResourceFarm

        ResourceFarm().start(timeout=timeout, callback=callback, parent=self)

    def partyLeader(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.party.PartyLeader import \
            PartyLeader

        PartyLeader().start(callback=callback, parent=self)

    def waitForMembersIdle(self, members, callback=None):
        from pyd2bot.logic.roleplay.behaviors.party.WaitForMembersIdle import \
            WaitForMembersIdle

        WaitForMembersIdle().start(members, callback=callback, parent=self)

    def waitForMembersToShow(self, members, callback=None):
        from pyd2bot.logic.roleplay.behaviors.party.WaitForMembersToShow import \
            WaitForMembersToShow

        WaitForMembersToShow().start(members, callback=callback, parent=self)

    def npcDialog(self, npcMapId, npcId, npcOpenDialogId, npcQuestionsReplies, useZaap=True, check_special_dest=True, callback=None):
        from pyd2bot.logic.roleplay.behaviors.npc.NpcDialog import NpcDialog

        def onNPCMapReached(code, err):
            Logger().info(f"NPC Map reached with error : {err}")
            if err:
                return callback(code, err)
            NpcDialog().start(npcMapId, npcId, npcOpenDialogId, npcQuestionsReplies, callback=callback, parent=self)

        if useZaap:
            self.autotripUseZaap(npcMapId, callback=onNPCMapReached)
        else:
            self.autoTrip(npcMapId, check_special_dest=check_special_dest, callback=onNPCMapReached)

    def getOutOfAnkarnam(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.GetOutOfAnkarnam import \
            GetOutOfAnkarnam

        GetOutOfAnkarnam().start(callback=callback, parent=self)

    def changeServer(self, newServerId, callback=None):
        from pyd2bot.logic.roleplay.behaviors.start.ChangeServer import \
            ChangeServer

        ChangeServer().start(newServerId, callback=callback, parent=self)

    def createNewCharacter(self, breedId, name=None, sex=False, callback=None):
        from pyd2bot.logic.roleplay.behaviors.start.CreateNewCharacter import \
            CreateNewCharacter

        CreateNewCharacter().start(breedId, name, sex, callback=callback, parent=self)

    def deleteCharacter(self, characterId, callback=None):
        from pyd2bot.logic.roleplay.behaviors.start.DeleteCharacter import \
            DeleteCharacter

        DeleteCharacter().start(characterId, callback=callback, parent=self)

    def treasureHunt(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.quest.ClassicTreasureHunt import \
            TreasureHunt

        TreasureHunt().start(callback=callback, parent=self)

    def botExchange(self, direction, target, items=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.exchange.BotExchange import \
            BotExchange

        BotExchange().start(direction, target, items, callback=callback, parent=self)

    def openBank(self, bankInfos=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bank.OpenBank import OpenBank

        OpenBank().start(bankInfos, callback=callback, parent=self)

    def retrieveRecipeFromBank(self, recipe, return_to_start=True, bankInfos=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bank.RetrieveRecipeFromBank import \
            RetrieveRecipeFromBank

        RetrieveRecipeFromBank().start(recipe, return_to_start, bankInfos, callback=callback, parent=self)

    def unloadInBank(self, return_to_start=True, bankInfos=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bank.UnloadInBank import \
            UnloadInBank

        UnloadInBank().start(return_to_start, bankInfos, callback=callback, parent=self)

    def on(self, event_id, callback, timeout=None, ontimeout=None, retryNbr=None, retryAction=None):
        return KernelEventsManager().on(
            event_id=event_id,
            callback=callback,
            timeout=timeout,
            ontimeout=ontimeout,
            retryNbr=retryNbr,
            retryAction=retryAction,
            once=False,
            originator=self,
        )

    def once(self, event_id, callback, timeout=None, ontimeout=None, retryNbr=None, retryAction=None):
        return KernelEventsManager().on(
            event_id=event_id,
            callback=callback,
            timeout=timeout,
            ontimeout=ontimeout,
            retryNbr=retryNbr,
            retryAction=retryAction,
            once=True,
            originator=self,
        )

    def onceMapProcessed(self, callback, args=[], mapId=None, timeout=None, ontimeout=None):
        return KernelEventsManager().onceMapProcessed(
            callback=callback, args=args, mapId=mapId, timeout=timeout, ontimeout=ontimeout, originator=self
        )

    def onceFramePushed(self, frameName, callback):
        return KernelEventsManager().onceFramePushed(frameName, callback, originator=self)

    def send(self, event_id, *args, **kwargs):
        return KernelEventsManager().send(event_id, *args, **kwargs)

    def hasListener(self, event_id):
        return KernelEventsManager().hasListener(event_id)

    def onEntityMoved(self, entityId, callback, timeout=None, ontimeout=None, once=False):
        return KernelEventsManager().onEntityMoved(
            entityId=entityId, callback=callback, timeout=timeout, ontimeout=ontimeout, once=once, originator=self
        )

    def onceFightSword(self, entityId, entityCell, callback, args=[]):
        return KernelEventsManager().onceFightSword(entityId, entityCell, callback, args=args, originator=self)
