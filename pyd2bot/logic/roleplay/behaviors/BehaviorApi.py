import json
import os
from typing import TYPE_CHECKING, Dict, List

from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.common.managers.MarketBid import MarketBid
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import TransitionTypeEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.dialog.LeaveDialogRequestMessage import (
    LeaveDialogRequestMessage,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
    from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper


__dir__ = os.path.dirname(os.path.abspath(__file__))


class BehaviorApi:
    ANKARNAM_AREA_ID = 45
    ASTRUB_AREA_ID = 95
    NEW_VALONIA_AREA_ID = 93
    SPECIAL_AREA_INFOS_NOT_FOUND_ERROR = 89091
    PLAYER_IN_FIGHT_ERROR = 89090
    CELESTIAL_SUBAREA_ID = 446

    def __init__(self) -> None:
        pass

    def travel_using_zaap(
        self,
        dstMapId,
        dstZoneId=None,
        withSaveZaap=False,
        maxCost=None,
        excludeMaps=[],
        check_special_dest=True,
        farm_resources_on_way=False,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.movement.AutoTripUseZaap import AutoTripUseZaap

        useZaap = True
        currVertex = PlayedCharacterManager().currVertex
        if currVertex.mapId == dstMapId:
            if dstZoneId is None or currVertex.zoneId == dstZoneId:
                Logger().info("Player already at the destination!")
                return callback(0, None)

        if not maxCost:
            maxCost = InventoryManager().inventory.kamas
            Logger().debug(f"Player max teleport cost is {maxCost}")

        dst_sub_area = SubArea.getSubAreaByMapId(dstMapId)
        if PlayedCharacterManager().currentSubArea.areaId == self.ANKARNAM_AREA_ID and dst_sub_area.areaId != self.ANKARNAM_AREA_ID:
            useZaap = False

        if PlayerManager().isBasicAccount() and not dst_sub_area.basicAccountAllowed:
            return callback(1, "Destination map is not allowed for basic accounts!")

        if (
            PlayedCharacterManager().currentSubArea.id == self.CELESTIAL_SUBAREA_ID
            and dst_sub_area.id != self.CELESTIAL_SUBAREA_ID
        ):
            Logger().info(f"Player is in celestial dimension, and wants to get out of there.")

            def onOutOfCelestialDim(code, err):
                if err:
                    return callback(code, f"Could not get player out of celestial dimension : {err}")
                self.travel_using_zaap(dstMapId, dstZoneId, withSaveZaap, maxCost, excludeMaps, callback=callback)

            return self.autoTrip(154010883, 1, callback=onOutOfCelestialDim)

        if not useZaap:
            return self.autoTrip(
                dstMapId, dstZoneId, farm_resources_on_way=farm_resources_on_way, callback=callback
            )

        from pyd2bot.misc.Localizer import Localizer

        path_to_dest_zaap = Localizer.findPathToClosestZaap(
            dstMapId, maxCost, excludeMaps=excludeMaps, onlyKnownZaap=False
        )
        if path_to_dest_zaap is None:
            Logger().warning(f"No dest zaap found for cost {maxCost} and map {dstMapId}!")
            return self.autoTrip(dstMapId, dstZoneId, farm_resources_on_way=farm_resources_on_way, callback=callback)

        if len(path_to_dest_zaap) == 0:
            dstZaapVertex = currVertex = PlayedCharacterManager().currVertex
        else:
            dstZaapVertex = path_to_dest_zaap[-1].dst

        def on_dst_zaap_unknown():
            Logger().debug(f"Dest zaap at vertex {dstZaapVertex} is not known ==> We need to travel to register it.")

            def onDstZaapTrip(code, err):
                if err:
                    Logger().error(f"Can't reach the dest zaap at {dstZaapVertex} : {err}")
                    return self.autoTrip(
                        dstMapId, dstZoneId, farm_resources_on_way=farm_resources_on_way, callback=callback
                    )
                if withSaveZaap:

                    def onDstZaapSaved(code, err):
                        if err:
                            return callback(code, err)
                        self.autoTrip(
                            dstMapId, dstZoneId, farm_resources_on_way=farm_resources_on_way, callback=callback
                        )

                    return self.save_zaap(onDstZaapSaved)
                self.autoTrip(dstMapId, dstZoneId, farm_resources_on_way=farm_resources_on_way, callback=callback)

            self.travel_using_zaap(
                dstZaapVertex.mapId,
                dstZaapVertex.zoneId,
                excludeMaps=excludeMaps + [dstZaapVertex.mapId],
                callback=onDstZaapTrip,
            )

        if not PlayedCharacterManager().isZaapKnown(dstZaapVertex.mapId):
            return on_dst_zaap_unknown()

        Logger().debug(
            f"Dst zaap at {dstZaapVertex} is found in known ZAAPS, traveling with zaaps to {dstMapId}, zoneId={dstZoneId}"
        )

        def onAutoTripUseZaapEnd(code, err):
            from pyd2bot.logic.roleplay.behaviors.teleport.UseZaap import UseZaap

            if err:
                if code == AutoTripUseZaap.NO_PATH_TO_DEST:
                    Logger().error(err)
                    Logger().info("Trying to reach the destination with classic auto trip as last resort.")
                    return self.autoTrip(
                        dstMapId, 
                        dstZoneId, 
                        farm_resources_on_way=farm_resources_on_way, 
                        callback=callback
                    )
                elif code == UseZaap.DST_ZAAP_NOT_KNOWN:
                    if PlayerManager().inHavenBag():
                        Logger().debug(f"Player is inside haven bag, we need to exit it before traveling!")
                        return self.toggle_haven_bag(False, lambda *_: on_dst_zaap_unknown())
                    return on_dst_zaap_unknown()

            return callback(code, err)

        AutoTripUseZaap().start(
            dstMapId,
            dstZoneId,
            dstZaapVertex.mapId,
            withSaveZaap=withSaveZaap,
            maxCost=maxCost,
            farm_resources_on_way=farm_resources_on_way,
            callback=onAutoTripUseZaapEnd,
            parent=self,
        )

    def autoTrip(
        self,
        dstMapId,
        dstZoneId=None,
        path: list["Edge"] = None,
        check_special_dest=True,
        farm_resources_on_way=False,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
        from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel

        Logger().info(f"Basic auto trip to map {dstMapId}, rpzone {dstZoneId} called.")
        if Kernel().fightContextFrame:
            Logger().error(f"Player is in Fight => Can't auto trip.")
            return callback(self.PLAYER_IN_FIGHT_ERROR, "Player is in Fight")

        AutoTrip(farm_resources_on_way).start(dstMapId, dstZoneId, path, callback=callback, parent=self)

    def travel_with_npc(self, infos, useZaap=True, callback=None, dstSubAreaName=""):
        Logger().info(f"Auto trip to a special destination ({dstSubAreaName}). Using zaap={useZaap}")

        def onNpcDialogEnd(code, err):
            if err:
                return callback(code, err)
            self.once_map_rendered(
                callback=lambda: callback(True, None),
                mapId=infos["landingMapId"],
            )

        self.npc_dialog(
            infos["npcMapId"],
            infos["npcId"],
            infos["openDialogActionId"],
            infos["replies"],
            useZaap=useZaap,
            callback=onNpcDialogEnd,
        )

    def changeMap(self, transition: "Transition" = None, edge: "Edge" = None, dstMapId=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import ChangeMap

        ChangeMap().start(transition, edge, dstMapId, callback=callback, parent=self)

    def toggle_haven_bag(self, wanted_state=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.teleport.ToggleHavenBag import ToggleHavenBag

        ToggleHavenBag().start(wanted_state=wanted_state, callback=callback, parent=self)

    def toggle_ride_mount(self, wanted_ride_state=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.mount.ToggleRideMount import ToggleRideMount

        ToggleRideMount().start(wanted_ride_state=wanted_ride_state, callback=callback, parent=self)

    def mapMove(
        self,
        destCell,
        exactDestination=True,
        forMapChange=False,
        mapChangeDirection=-1,
        callback=None,
        cellsblacklist=[],
    ):
        from pyd2bot.logic.roleplay.behaviors.movement.MapMove import MapMove

        MapMove().start(
            destCell,
            exactDestination=exactDestination,
            forMapChange=forMapChange,
            mapChangeDirection=mapChangeDirection,
            callback=callback,
            cellsblacklist=cellsblacklist,
            parent=self,
        )

    def watch_fight_sequence(self, callback):
        from pyd2bot.logic.fight.behaviors.WatchFightSequence import WatchFightSequence

        WatchFightSequence().start(parent=self, callback=callback)

    def fight_move(self, path_cellIds: List[int], callback=None):
        from pyd2bot.logic.fight.behaviors.fight_turn.FightMove import FightMoveBehavior

        FightMoveBehavior(path_cellIds).start(callback=callback, parent=self)

    def cast_spell(self, target_cellId: int, callback=None):
        from pyd2bot.logic.fight.behaviors.fight_turn.CastSpell import CastSpell

        CastSpell(target_cellId).start(callback=callback, parent=self)

    def use_items_of_type(self, type_id, callback=None):
        from pyd2bot.logic.roleplay.behaviors.inventory.UseItemsByType import UseItemsByType

        b = UseItemsByType(type_id)
        b.start(callback=callback)
        return b

    def use_item(self, item: "ItemWrapper", qty: int, callback=None):
        from pyd2bot.logic.roleplay.behaviors.inventory.UseItem import UseItem

        b = UseItem(item, qty)
        b.start(callback=callback, parent=self)
        return b

    def requestMapData(self, mapId=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.RequestMapData import RequestMapData

        RequestMapData().start(mapId, callback=callback, parent=self)

    def auto_resurrect(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.misc.Resurrect import Resurrect

        b = Resurrect()
        b.start(callback=callback, parent=self)
        return b

    def attackMonsters(self, entityId, callback=None):
        from pyd2bot.logic.roleplay.behaviors.fight.AttackMonsters import AttackMonsters

        AttackMonsters().start(entityId, callback=callback, parent=self)

    def farmFights(self, timeout=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.fight.GroupLeaderFarmFights import GroupLeaderFarmFights

        GroupLeaderFarmFights().start(timeout=timeout, callback=callback, parent=self)

    def muleFighter(self, leader, callback=None):
        from pyd2bot.logic.roleplay.behaviors.fight.MuleFighter import MuleFighter

        MuleFighter().start(leader, callback=callback, parent=self)

    def save_zaap(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.teleport.SaveZaap import SaveZaap

        SaveZaap().start(callback=callback, parent=self)

    def useZaap(self, dstMapId, saveZaap=False, callback=None):
        from pyd2bot.logic.roleplay.behaviors.teleport.UseZaap import UseZaap

        UseZaap().start(dstMapId, saveZaap, callback=callback, parent=self)

    def use_rappel_potion(self, callback):
        for iw in InventoryManager().inventory.getView("storageConsumables").content:
            if iw.objectGID == DataEnum.RAPPEL_POTION_GUID:
                self.useTeleportItem(iw, callback=callback)
                return True
        return False

    def put_pet_mount(self, callback):
        from pyd2bot.logic.roleplay.behaviors.mount.PutPetsMount import PutPetsMount

        b = PutPetsMount()
        b.start(callback=callback, parent=self)
        return b

    def use_skill(
        self,
        ie=None,
        cell=None,
        exactDestination=False,
        waitForSkillUsed=True,
        elementId=None,
        skilluid=None,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill

        UseSkill().start(
            ie, cell, exactDestination, waitForSkillUsed, elementId, skilluid, callback=callback, parent=self
        )

    def soloFarmFights(
        self, path, fightPerMinute=1, fightPartyMembers=None, monsterLvlCoefDiff=None, timeout=None, callback=None
    ):
        from pyd2bot.logic.roleplay.behaviors.fight.SoloFarmFights import SoloFarmFights

        SoloFarmFights(path, fightPerMinute, fightPartyMembers, monsterLvlCoefDiff, timeout).start(
            callback=callback, parent=self
        )

    def resourceFarm(self, path, jobFilter, timeout=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.farm.ResourceFarm import ResourceFarm

        ResourceFarm(path, jobFilter, timeout).start(callback=callback, parent=self)

    def partyLeader(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.party.PartyLeader import PartyLeader

        PartyLeader().start(callback=callback, parent=self)

    def take_treasure_hunt_quest(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.quest.treasure_hunt.TakeTreasureHuntQuest import TakeTreasureHuntQuest

        TakeTreasureHuntQuest().start(callback=callback, parent=self)
    
    def waitForMembersIdle(self, members, leader, callback=None):
        from pyd2bot.logic.roleplay.behaviors.party.WaitForMembersIdle import WaitForMembersIdle

        WaitForMembersIdle().start(members, leader, callback=callback, parent=self)

    def waitForMembersToShow(self, members, callback=None):
        from pyd2bot.logic.roleplay.behaviors.party.WaitForMembersToShow import WaitForMembersToShow

        WaitForMembersToShow().start(members, callback=callback, parent=self)

    def npc_dialog(
        self,
        npcMapId,
        npcId,
        npcOpenDialogId,
        npcQuestionsReplies,
        useZaap=True,
        check_special_dest=True,
        farm_resources_on_way=False,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.npc.NpcDialog import NpcDialog

        def onNPCMapReached(code, err):
            Logger().info(f"NPC Map reached with error : {err}")
            if err:
                return callback(code, err)
            NpcDialog().start(npcMapId, npcId, npcOpenDialogId, npcQuestionsReplies, callback=callback, parent=self)

        if useZaap:
            self.travel_using_zaap(npcMapId, callback=onNPCMapReached)
        else:
            self.autoTrip(
                npcMapId,
                check_special_dest=check_special_dest,
                farm_resources_on_way=farm_resources_on_way,
                callback=onNPCMapReached,
            )

    def getOutOfAnkarnam(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.GetOutOfAnkarnam import GetOutOfAnkarnam

        GetOutOfAnkarnam().start(callback=callback, parent=self)

    def changeServer(self, newServerId, callback=None):
        from pyd2bot.logic.roleplay.behaviors.start.ChangeServer import ChangeServer

        ChangeServer().start(newServerId, callback=callback, parent=self)

    def createNewCharacter(self, breedId, name=None, sex=False, callback=None):
        from pyd2bot.logic.roleplay.behaviors.start.CreateNewCharacter import CreateNewCharacter

        CreateNewCharacter().start(breedId, name, sex, callback=callback, parent=self)

    def deleteCharacter(self, characterId, callback=None):
        from pyd2bot.logic.roleplay.behaviors.start.DeleteCharacter import DeleteCharacter

        DeleteCharacter().start(characterId, callback=callback, parent=self)

    def treasureHunt(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.quest.treasure_hunt.ClassicTreasureHunt import TreasureHunt

        TreasureHunt().start(callback=callback, parent=self)

    def useTeleportItem(self, iw, callback=None):
        from pyd2bot.logic.roleplay.behaviors.inventory.UseTeleportItem import UseTeleportItem

        UseTeleportItem().start(iw, callback=callback, parent=self)

    def botExchange(self, direction, target, items=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.exchange.BotExchange import BotExchange

        BotExchange().start(direction, target, items, callback=callback, parent=self)

    def open_bank(self, bankInfos=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bank.OpenBank import OpenBank

        OpenBank().start(bankInfos, callback=callback, parent=self)

    def retrieve_recipe_from_bank(self, recipe, return_to_start=True, bankInfos=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bank.RetrieveRecipeFromBank import RetrieveRecipeFromBank

        RetrieveRecipeFromBank().start(recipe, return_to_start, bankInfos, callback=callback, parent=self)

    def unload_in_bank(self, return_to_start=True, bankInfos=None, leave_bank_open=False, items_gid_to_keep=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bank.UnloadInBank import UnloadInBank

        UnloadInBank().start(return_to_start, bankInfos, leave_bank_open, items_gid_to_keep, callback=callback, parent=self)

    def retrieve_sell(self, type_batch_size, items_gid_to_keep=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.RetrieveSellUpdate import RetrieveSellUpdate

        b = RetrieveSellUpdate(type_batch_size=type_batch_size, items_gid_to_keep=items_gid_to_keep)
        b.start(callback=callback, parent=self)
        return b

    def edit_bid_price(self, bid: MarketBid, new_price: int, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.EditBidPrice import EditBidPrice

        b = EditBidPrice(bid, new_price)
        b.start(callback=callback, parent=self)
        return b

    def place_bid(self, object_gid: int, quantity: int, price: int, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.PlaceBid import PlaceBid

        b = PlaceBid(object_gid, quantity, price)
        b.start(callback=callback, parent=self)
        return b

    def open_market(
        self, from_gid=None, from_type=None, exclude_market_at_maps=None, mode="sell", item_level=200, callback=None
    ):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.OpenMarket import OpenMarket

        b = OpenMarket(
            from_gid=from_gid,
            from_object_category=from_type,
            mode=mode,
            exclude_market_at_maps=exclude_market_at_maps,
            item_level=item_level,
        )
        b.start(callback=callback, parent=self)
        return b

    def close_market(self, callback):
        if Kernel().marketFrame._market_type_open is None:
            Logger().warning("No market is open!")
            return callback(0, None)

        def _on_market_close(code, error):
            if error:
                return callback(code, f"Market close failed with error [{code}] {error}")
            Kernel().marketFrame.reset_state()
            callback(0, None)

        self.close_dialog(_on_market_close)

    def close_dialog(self, handler, timeout=10):
        self.once(
            event_id=KernelEvent.LeaveDialog,
            callback=lambda _: handler(0, None),
            timeout=timeout,
            ontimeout=lambda _: handler(1, "close dialog timed out!"),
        )
        ConnectionsHandler().send(LeaveDialogRequestMessage())
        InactivityManager().activity()

    def goto_market(self, market_gfx_id, exclude_market_at_maps=None, item_level=200, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.GoToMarket import GoToMarket

        b = GoToMarket(market_gfx_id, exclude_market_at_maps, item_level)
        b.start(callback=callback, parent=self)
        return b

    def retrieve_items_from_bank(
        self,
        type_batch_size: Dict[int, int],
        gid_batch_size: Dict[int, int],
        return_to_start: bool = False,
        bank_infos=None,
        max_item_level=200,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.bank.RetrieveFromBank import RetrieveFromBank

        b = RetrieveFromBank(type_batch_size, gid_batch_size, return_to_start, bank_infos, max_item_level)
        b.start(callback=callback, parent=self)
        return b

    def pull_bank_items(self, items_uids, quantities, callback):
        self.once(KernelEvent.InventoryWeightUpdate, lambda *_: callback())
        Logger().debug(f"Retrieving items: UIDs={items_uids}, Quantities={quantities}")
        Kernel().exchangeManagementFrame.exchangeObjectTransferListWithQuantityToInv(items_uids, quantities)

    def retrieve_kamas_from_bank(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bank.RetrieveKamasFromBank import RetrieveKamasFromBank

        RetrieveKamasFromBank().start(callback=callback, parent=self)

    def collect_all_map_resources(self, job_filters=[], callback=None):
        from pyd2bot.logic.roleplay.behaviors.farm.CollectAllMapResources import CollectAllMapResources

        CollectAllMapResources(job_filters).start(callback=callback, parent=self)

    def sell_items(self, gid_batch_size: Dict[int, int] = None, type_batch_size: Dict[int, int] = None, callback=None):
        """
        Sell items from inventory in the marketplace.
        Automatically travels to marketplace and lists items at competitive prices.

        Args:
            items_to_sell: List of tuples (object_gid, quantity)
            callback: Completion callback function
        """
        from pyd2bot.logic.roleplay.behaviors.bidhouse.SellItemsFromBag import SellItemsFromBag

        behavior = SellItemsFromBag(gid_batch_size, type_batch_size)
        behavior.start(callback=callback, parent=self)
        return behavior

    def update_market_bids(self, resource_type, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.UpdateMarketBids import UpdateMarketBids

        b = UpdateMarketBids(market_type=resource_type)
        b.start(callback=callback, parent=self)
        return b

    def on(self, event_id, callback, timeout=None, ontimeout=None, retryNbr=None, retryAction=None, once=False):
        return KernelEventsManager().on(
            event_id=event_id,
            callback=callback,
            timeout=timeout,
            ontimeout=ontimeout,
            retry_count=retryNbr,
            retry_action=retryAction,
            once=once,
            originator=self,
        )

    def once(self, event_id, callback, timeout=None, ontimeout=None, retry_nbr=None, retry_action=None):
        return self.on(
            event_id,
            callback,
            timeout=timeout,
            ontimeout=ontimeout,
            retryNbr=retry_nbr,
            retryAction=retry_action,
            once=True,
        )

    def on_multiple(self, listeners):
        for event_id, callback, kwargs in listeners:
            self.on(event_id, callback, **kwargs)

    def once_map_rendered(self, callback, args=[], mapId=None, timeout=None, ontimeout=None):
        return KernelEventsManager().onceMapProcessed(
            callback=callback, args=args, mapId=mapId, timeout=timeout, ontimeout=ontimeout, originator=self
        )

    def once_frame_pushed(self, frameName, callback, args=[]):
        return KernelEventsManager().onceFramePushed(frameName, callback, args=args, originator=self)

    def send(self, event_id, *args, **kwargs):
        return KernelEventsManager().send(event_id, *args, **kwargs)

    def has_listener(self, event_id):
        return KernelEventsManager().has_listener(event_id)

    def onEntityMoved(self, entityId, callback, timeout=None, ontimeout=None, once=False):
        return KernelEventsManager().onEntityMoved(
            entityId=entityId, callback=callback, timeout=timeout, ontimeout=ontimeout, once=once, originator=self
        )

    def onceFightSword(self, entityId, entityCell, callback, args=[]):
        return KernelEventsManager().onceFightSword(entityId, entityCell, callback, args=args, originator=self)
