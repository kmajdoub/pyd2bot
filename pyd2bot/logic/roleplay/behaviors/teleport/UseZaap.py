from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.datacenter.jobs.Skill import Skill
from pydofus2.com.ankamagames.dofus.internalDatacenter.taxi.TeleportDestinationWrapper import \
    TeleportDestinationWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import PathFinding


class UseZaap(AbstractBehavior):
    ZAAP_NOTFOUND = 255898
    DST_ZAAP_NOT_KNOWN = 265574
    INSUFFICIENT_KAMAS = 788888
    ZAAP_DIALOG_OPEN_TIMEOUT = 788889
    ZAAP_USE_ERROR = 788890
    MAX_TELEPORT_RETRIES = 2
    
    def __init__(self) -> None:
        super().__init__()
        self._teleport_retry_count = 0

    def run(self, dstMapId, bsaveZaap=False) -> bool:
        Logger().debug(f"Use zaap to dest {dstMapId} called")
        self.dst_mapId = dstMapId
        self.bsaveZaap = bsaveZaap
        self.teleportDestinationListener: Listener = None
        if not PlayedCharacterManager().isZaapKnown(dstMapId):
            return self.finish(self.DST_ZAAP_NOT_KNOWN, "Destination zaap is not a known zaap!")
        if Kernel().interactiveFrame:
            self._open_current_map_zaap_dialog()
        else:
            self.once_frame_pushed("RoleplayInteractivesFrame", self._open_current_map_zaap_dialog)

    def _on_server_info(self, event, msgId, msgType, textId, msgContent, params):
        if textId == ServerNotificationEnum.KAMAS_LOST:
            KernelEventsManager().send(KernelEvent.KamasLostFromTeleport, int(params[0]))

    def _open_current_map_zaap_dialog(self):
        self.zaapIe = Kernel().interactiveFrame.getZaapIe()
        if not self.zaapIe:
            return self.finish(self.ZAAP_NOTFOUND, "No Zaap IE found in the current Map!")
        if self._check_zaap_rp_zone():
            return
        self.once(
            KernelEvent.TeleportDestinationList,
            self._on_teleport_destination_list,
            timeout=10,
            ontimeout=self._on_zaap_skill_use_error,
            retry_nbr=2,
            retry_action=self._use_zaap_skill
        )
        self._use_zaap_skill()
    
    def _check_zaap_rp_zone(self):
        self.zaapSkill = Skill.getSkillById(self.zaapIe.element.enabledSkills[0].skillId)
        self.nearestCellToZaapIE = self._get_nearest_cell_to_zaap()
        zaapIeReachable = self.nearestCellToZaapIE is not None and self.nearestCellToZaapIE.distanceTo(self.zaapIe.position) <= self.zaapSkill.range
        if not zaapIeReachable:
            Logger().error("Zaap is not reachable, maybe its in a different rp zone than the player!")
            zaapLinkedRpZone = MapDisplayManager().dataMap.cells[self.zaapIe.position.cellId].linkedZone
            playerLinkedRpZone = PlayedCharacterManager().currentZoneRp
            currMapVertices = WorldGraph().getVertices(PlayedCharacterManager().currentMap.mapId)
            Logger().debug(f"Current map vertices: {currMapVertices}")
            if zaapLinkedRpZone != playerLinkedRpZone:
                Logger().warning(f"Zaap is in a different rp zone than the player, zaap rp zone: {zaapLinkedRpZone}, player rp zone: {playerLinkedRpZone}")
                Logger().debug(f"Traveling to the zaap rp zone {zaapLinkedRpZone} ...")
                self.autoTrip(PlayedCharacterManager().currentMap.mapId, zaapLinkedRpZone, callback=self.onZaapRpZoneReached)
                return True
        return False
            
    def _on_zaap_skill_use_error(self, listener=None):
        Logger().debug("Maybe Zaap is in a different rp zone than the player, wil check that in a sec ...")
        if self._check_zaap_rp_zone():
            return
        self.finish(self.ZAAP_USE_ERROR, "Zaap is in same map as the player but is not usable!")

    def onZaapRpZoneReached(self, code, err):
        if err:
            self.finish(code, err)
            return
        self.teleportDestinationListener = self.once(
            KernelEvent.TeleportDestinationList,
            self._on_teleport_destination_list,
            timeout=10,
            ontimeout=self._on_zaap_skill_use_error,
            retry_nbr=2,
            retry_action=self._use_zaap_skill
        )
        self._use_zaap_skill()

    def _get_nearest_cell_to_zaap(self):
        playerEntity = PlayedCharacterManager().entity
        if playerEntity is None:
            Logger().error("Player entity not found, while trying to find nearest cell to Zaap!")
            return None
        movePath = PathFinding().findPath(playerEntity.position, self.zaapIe.position)
        if movePath is None:
            return None
        return movePath.end
        
    def _use_zaap_skill(self):
        self.use_skill(ie=self.zaapIe, waitForSkillUsed=False, callback=self._on_zaap_skill_used)
    
    def _on_zaap_skill_used(self, code, err):
        if err:
            if self.teleportDestinationListener:
                self.teleportDestinationListener.delete()
            self._on_zaap_skill_use_error()
    
    def _retry_teleport(self, listener):
        Logger().debug(f"Retrying teleport attempt {self._teleport_retry_count + 1} of {self.MAX_TELEPORT_RETRIES}")
        self._teleport_retry_count += 1
        if self._teleport_retry_count <= self.MAX_TELEPORT_RETRIES:
            self.once_map_rendered(
                self._on_dest_map_processed,
                timeout=10,
                ontimeout=self._retry_teleport if self._teleport_retry_count < self.MAX_TELEPORT_RETRIES else lambda: self._handle_error(
                    self.ZAAP_USE_ERROR,
                    f"Failed to process destination map after {self.MAX_TELEPORT_RETRIES} attempts"
                )
            )
            self.once(KernelEvent.ServerTextInfo, self._on_server_info)
            Kernel().zaapFrame.sendTeleportRequest(
                self._current_cost, 
                self._current_ttype,
                self._current_dest_type, 
                self.dst_mapId
            )
        else:
            self._handle_error(
                self.ZAAP_USE_ERROR,
                f"Failed to process destination map after {self.MAX_TELEPORT_RETRIES} attempts"
            )

    def _on_teleport_destination_list(self, event, destinations: list[TeleportDestinationWrapper], ttype):
        Logger().debug(f"Zaap teleport destinations received.")
        for dst in destinations:
            if dst.mapId == self.dst_mapId:
                if dst.cost > PlayedCharacterManager().characteristics.kamas:
                    self._handle_error(
                        self.INSUFFICIENT_KAMAS,
                        f"Insufficient kamas to take zaap, player kamas ({PlayedCharacterManager().characteristics.kamas}), teleport cost ({dst.cost})"
                    )
                    return
                self._current_cost = dst.cost
                self._current_ttype = ttype
                self._current_dest_type = dst.destinationType
                self._teleport_retry_count = 0
                
                self.once_map_rendered(
                    self._on_dest_map_processed,
                    timeout=10,
                    ontimeout=self._retry_teleport
                )
                self.once(KernelEvent.ServerTextInfo, self._on_server_info)
                Kernel().zaapFrame.sendTeleportRequest(dst.cost, ttype, dst.destinationType, dst.mapId)
                return 
        else:
            self._handle_error(
                self.DST_ZAAP_NOT_KNOWN,
                f"Zaap {self.dst_mapId} not in available destinations: {[d.mapId for d in destinations]}"
            )

    def _handle_error(self, code, error):
        self.close_dialog(lambda *_: self.finish(code, error))
    
    def _on_zaap_saved(self, code, err):
        if err:
            Logger().error(f"Save zaap failed for reason: {err}")
        self.finish(0)
    
    def _on_dest_map_processed(self, event=None):
        KernelEventsManager().send(KernelEvent.ZAAP_TELEPORT)
        if self.bsaveZaap and Kernel().zaapFrame.spawnMapId != PlayedCharacterManager().currentMap.mapId:
            return self.save_zaap(self._on_zaap_saved)
        return self.finish(0)
