import os
from typing import TYPE_CHECKING

from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.common.managers.MarketBid import MarketBid
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.dialog.LeaveDialogRequestMessage import (
    LeaveDialogRequestMessage,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
    from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
    from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
    from pydofus2.com.ankamagames.dofus.internalDatacenter.spells.SpellWrapper import SpellWrapper


__dir__ = os.path.dirname(os.path.abspath(__file__))


class BehaviorApi:
    SPECIAL_AREA_INFOS_NOT_FOUND_ERROR = 89091
    PLAYER_IN_FIGHT_ERROR = 89090

    def __init__(self) -> None:
        pass

    def autoTrip(
        self,
        dstMapId=None,
        dstZoneId=None,
        path: list["Edge"] = None,
        farm_resources_on_way=False,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip

        AutoTrip(farm_resources_on_way).start(dstMapId, dstZoneId, path, callback=callback, parent=self)

    def travel_with_npc(self, infos, callback=None, dstSubAreaName=""):
        Logger().info(f"Auto trip to a special destination ({dstSubAreaName}).")

        def onNpcDialogEnd(code, err):
            if err:
                return callback(code, err)
            self.once_map_rendered(
                callback=lambda: callback(True, None),
                mapId=infos["landingMapId"],
            )

        self._on_npc_dialog_end_callback = onNpcDialogEnd

        self.npc_dialog(
            infos["npcMapId"],
            infos["npcId"],
            infos["openDialogActionId"],
            infos["replies"],
            callback=self._on_npc_dialog_end_callback,
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

    def map_move_to_cell(
        self,
        destCell,
        exact_destination=True,
        forMapChange=False,
        mapChangeDirection=-1,
        callback=None,
        cellsblacklist=[],
    ):
        from pyd2bot.logic.roleplay.behaviors.movement.MapMove import MapMove

        MapMove(
            destCell,
            exactDestination=exact_destination,
            forMapChange=forMapChange,
            mapChangeDirection=mapChangeDirection,
            cellsblacklist=cellsblacklist,
        ).start(
            callback=callback,
            parent=self,
        )

    def watch_fight_sequence(self, callback):
        from pyd2bot.logic.fight.behaviors.WatchFightSequence import WatchFightSequence

        WatchFightSequence().start(parent=self, callback=callback)

    def fight_move(self, path_cellIds: list[int], callback=None):
        from pyd2bot.logic.fight.behaviors.fight_turn.FightMove import FightMoveBehavior

        FightMoveBehavior(path_cellIds).start(callback=callback, parent=self)

    def cast_spell(self, spellw: "SpellWrapper", target_cellId: int, callback=None):
        from pyd2bot.logic.fight.behaviors.fight_turn.CastSpell import CastSpell

        CastSpell(spellw, target_cellId).start(callback=callback, parent=self)

    def use_items_of_type(self, type_id, callback=None):
        from pyd2bot.logic.roleplay.behaviors.inventory.UseItemsByType import UseItemsByType

        UseItemsByType(type_id).start(callback=callback)

    def use_item(self, item: "ItemWrapper", qty: int, callback=None):
        from pyd2bot.logic.roleplay.behaviors.inventory.UseItem import UseItem

        UseItem(item, qty).start(callback=callback, parent=self)

    def requestMapData(self, mapId=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.RequestMapData import RequestMapData

        RequestMapData().start(mapId, callback=callback, parent=self)

    def auto_resurrect(self, callback=None):
        from pyd2bot.logic.roleplay.behaviors.misc.Resurrect import Resurrect

        Resurrect().start(callback=callback, parent=self)

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

    def teleport_using_havenbag(self, destMapId, callback):
        from pyd2bot.logic.roleplay.behaviors.teleport.TeleportUsingHavenBag import TeleportUsingHavenbag

        TeleportUsingHavenbag(destMapId).start(callback=callback, parent=self)

    def use_rappel_potion(self, callback):
        for iw in InventoryManager().inventory.getView("storageConsumables").content:
            if iw.objectGID == DataEnum.RAPPEL_POTION_GUID:
                self.useTeleportItem(iw, callback=callback)
                return True
        return False

    def action_map_change(self, dst_mapId, transition_cell, callback):
        from pyd2bot.logic.roleplay.behaviors.movement.ActionMapChange import ActionMapChange

        ActionMapChange(dst_mapId, transition_cell).start(callback=callback, parent=self)

    def scroll_map_change(self, dst, tr_mapid, cell, direction, callback):
        from pyd2bot.logic.roleplay.behaviors.movement.ScrollMapChange import ScrollMapChange

        ScrollMapChange(dst, tr_mapid, cell, direction).start(callback=callback, parent=self)

    def put_pet_mount(self, callback):
        from pyd2bot.logic.roleplay.behaviors.mount.PutPetsMount import PutPetsMount

        PutPetsMount().start(callback=callback, parent=self)

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
        farm_resources_on_way=False,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.npc.NpcDialog import NpcDialog

        if PlayedCharacterManager().currentMap.mapId == npcMapId:
            NpcDialog().start(npcMapId, npcId, npcOpenDialogId, npcQuestionsReplies, callback=callback, parent=self)
        else:
            def _on_npc_reached(code, err):
                Logger().info(f"NPC Map reached with result : {err}")
                if err:
                    return callback(code, err)
                NpcDialog().start(npcMapId, npcId, npcOpenDialogId, npcQuestionsReplies, callback=callback, parent=self)
            
            self._on_npc_reached_callback = _on_npc_reached
            
            self.autoTrip(
                npcMapId,
                farm_resources_on_way=farm_resources_on_way,
                callback=self._on_npc_reached_callback,
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

    def unload_in_bank(
        self, return_to_start=True, bankInfos=None, leave_bank_open=False, items_gid_to_keep=None, callback=None
    ):
        from pyd2bot.logic.roleplay.behaviors.bank.UnloadInBank import UnloadInBank

        UnloadInBank().start(
            return_to_start, bankInfos, leave_bank_open, items_gid_to_keep, callback=callback, parent=self
        )

    def retrieve_sell(self, type_batch_size=None, items_gid_to_keep=None, return_to_start=True, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.RetrieveSellUpdate import RetrieveSellUpdate

        RetrieveSellUpdate(type_batch_size=type_batch_size, items_gid_to_keep=items_gid_to_keep, return_to_start=return_to_start).start(
            callback=callback, parent=self
        )

    def edit_bid_price(self, bid: MarketBid, new_price: int, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.EditBidPrice import EditBidPrice

        EditBidPrice(bid, new_price).start(callback=callback, parent=self)

    def place_bid(self, object_gid: int, quantity: int, price: int, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.PlaceBid import PlaceBid

        PlaceBid(object_gid, quantity, price).start(callback=callback, parent=self)

    def open_market(
        self, from_gid=None, from_type=None, exclude_market_at_maps=None, mode="sell", item_level=None, callback=None
    ):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.OpenMarket import OpenMarket

        OpenMarket(
            from_gid=from_gid,
            from_object_category=from_type,
            mode=mode,
            exclude_market_at_maps=exclude_market_at_maps,
            item_level=item_level,
        ).start(callback=callback, parent=self)

    def astar_find_path(self, dst_map_id, linked_zone=None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.movement.AstarPathFinder import AstarPathFinder

        AstarPathFinder(dst_map_id, linked_zone=linked_zone).start(callback=callback, parent=self)

    def close_market(self, callback):
        if not Kernel().marketFrame:
            Logger().warning("No market frame found!")
            return

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
            callback=lambda *_: handler(0, None),
            timeout=timeout,
            ontimeout=lambda *_: handler(1, "close dialog timed out!"),
        )
        ConnectionsHandler().send(LeaveDialogRequestMessage())
        InactivityManager().activity()

    def goto_market(self, market_gfx_id, exclude_market_at_maps=None, item_level=200, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.GoToMarket import GoToMarket

        GoToMarket(market_gfx_id, exclude_market_at_maps, item_level).start(callback=callback, parent=self)

    def interactive_map_change(self, dst_map_id: int, ie_elem_id: int, skill_id: int, cell_id: int, callback):
        from pyd2bot.logic.roleplay.behaviors.movement.InteractiveMapChange import InteractiveMapChange

        InteractiveMapChange(dst_map_id, ie_elem_id, skill_id, cell_id).start(callback=callback, parent=self)

    def retrieve_items_from_bank(
        self,
        type_batch_size: dict[int, int],
        gid_batch_size: dict[int, int],
        return_to_start: bool = False,
        bank_infos=None,
        max_item_level=200,
        callback=None,
    ):
        from pyd2bot.logic.roleplay.behaviors.bank.RetrieveFromBank import RetrieveFromBank

        RetrieveFromBank(type_batch_size, gid_batch_size, return_to_start, bank_infos, max_item_level).start(
            callback=callback, parent=self
        )

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

    def sell_items(self, gid_batch_size: dict[int, int] = None, type_batch_size: dict[int, int] = None, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.SellItemsFromBag import SellItemsFromBag

        SellItemsFromBag(gid_batch_size, type_batch_size).start(callback=callback, parent=self)

    def update_market_bids(self, resource_type, callback=None):
        from pyd2bot.logic.roleplay.behaviors.bidhouse.UpdateMarketBids import UpdateMarketBids

        UpdateMarketBids(market_type=resource_type).start(callback=callback, parent=self)

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

    def clearListeners(self):
        KernelEventsManager().clear_all_by_origin(self)
