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
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph
from pydofus2.com.ankamagames.dofus.network.messages.game.dialog.LeaveDialogRequestMessage import \
    LeaveDialogRequestMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import PathFinding


class UseZaap(AbstractBehavior):
    ZAAP_NOTFOUND = 255898
    DST_ZAAP_NOT_KNOWN = 265574
    NOT_RICH_ENOUGH = 788888
    ZAAP_DIALOG_OPEN_TIMEOUT = 788889
    ZAAP_USE_ERROR = 788890
    
    
    def __init__(self) -> None:
        super().__init__()

    def run(self, dstMapId, bsaveZaap=False) -> bool:
        Logger().debug(f"Use zaap to dest {dstMapId} called")
        self.dstMapId = dstMapId
        self.bsaveZaap = bsaveZaap
        self.teleportDestinationListener: Listener = None
        if not PlayedCharacterManager().isZaapKnown(dstMapId):
            return self.finish(self.DST_ZAAP_NOT_KNOWN, "Destination zaap is not a known zaap!")
        if Kernel().interactiveFrame:
            self.openCurrMapZaapDialog()
        else:
            self.onceFramePushed("RoleplayInteractivesFrame", self.openCurrMapZaapDialog)

    def onServerInfo(self, event, msgId, msgType, textId, msgContent, params):
        if textId == ServerNotificationEnum.KAMAS_LOST:
            KernelEventsManager().send(KernelEvent.KamasLostFromTeleport, int(params[0]))

    def openCurrMapZaapDialog(self):
        self.zaapIe = Kernel().interactiveFrame.getZaapIe()
        if not self.zaapIe:
            return self.finish(self.ZAAP_NOTFOUND, "No Zaap IE found in the current Map!")
        if self.checkZaapRpZone():
            return
        self.once(
            KernelEvent.TeleportDestinationList,
            self.onTeleportDestinationList,
            timeout=10,
            ontimeout=self.onZaapSkillUseFailed,
            retryNbr=2,
            retryAction=self.useZaapSkill
        )
        self.useZaapSkill()
    
    def checkZaapRpZone(self):
        self.zaapSkill = Skill.getSkillById(self.zaapIe.element.enabledSkills[0].skillId)
        self.nearestCellToZaapIE = self.getNearestCellToZaap()
        zaapIeReachable = self.nearestCellToZaapIE is not None and self.nearestCellToZaapIE.distanceTo(self.zaapIe.position) <= self.zaapSkill.range
        if not zaapIeReachable:
            Logger().error("Zaap is not reachable, maybe its in a different rp zone than the player!")
            zaapLinkedRpZone = MapDisplayManager().dataMap.cells[self.zaapIe.position.cellId].linkedZone
            playerLinkedRpZone = PlayedCharacterManager().currentZoneRp
            currMapVertices = WorldGraph().getVertices(PlayedCharacterManager().currentMap.mapId)
            Logger().debug(f"Current map vertices: {currMapVertices}")
            if zaapLinkedRpZone != playerLinkedRpZone:
                Logger().warning(f"Zaap is in a different rp zone than the player, zaap rp zone: {zaapLinkedRpZone}, player rp zone: {playerLinkedRpZone}")
                Logger().debug(f"Auto traveling to zaap rp zone {zaapLinkedRpZone}")
                self.autoTrip(PlayedCharacterManager().currentMap.mapId, zaapLinkedRpZone, callback=self.onZaapRpZoneReached)
                return True
        return False
            
    def onZaapSkillUseFailed(self, listener=None):
        Logger().debug("maybe Zaap in a different rp zone than the player")
        if self.checkZaapRpZone():
            return
        self.finish(self.ZAAP_USE_ERROR, "Zaap is in same map as the player but is not usable!")

    def onZaapRpZoneReached(self, code, err):
        if err:
            self.finish(code, err)
            return
        self.teleportDestinationListener = self.once(
            KernelEvent.TeleportDestinationList,
            self.onTeleportDestinationList,
            timeout=10,
            ontimeout=self.onZaapSkillUseFailed,
            retryNbr=2,
            retryAction=self.useZaapSkill
        )
        self.useZaapSkill()

    def getNearestCellToZaap(self):
        playerEntity = PlayedCharacterManager().entity
        if playerEntity is None:
            Logger().error("Player entity not found, while trying to find nearest cell to Zaap!")
            return None
        movePath = PathFinding().findPath(playerEntity.position, self.zaapIe.position)
        if movePath is None:
            return None
        return movePath.end
        
    def useZaapSkill(self):
        self.useSkill(ie=self.zaapIe, waitForSkillUsed=False, callback=self.onZaapSkillUsed)
    
    def onZaapSkillUsed(self, code, err):
        if err:
            if self.teleportDestinationListener:
                self.teleportDestinationListener.delete()
            self.onZaapSkillUseFailed()
        
    def onTeleportDestinationList(self, event, destinations: list[TeleportDestinationWrapper], ttype):
        Logger().debug(f"Zaap teleport destinations received.")
        for dst in destinations:
            if dst.mapId == self.dstMapId:
                if dst.cost > PlayedCharacterManager().characteristics.kamas:
                    ConnectionsHandler().send(LeaveDialogRequestMessage())
                    err = f"Don't have enough kamas to take zaap, player kamas ({PlayedCharacterManager().characteristics.kamas}), teleport cost ({dst.cost})!"
                    return self.on(
                        KernelEvent.LeaveDialog,
                        lambda e: self.finish(self.NOT_RICH_ENOUGH, err),
                    )
                self.onceMapProcessed(self.onDestMapProcessed)
                self.on(KernelEvent.ServerTextInfo, self.onServerInfo)
                return Kernel().zaapFrame.teleportRequest(dst.cost, ttype, dst.destinationType, dst.mapId)
        else:
            ConnectionsHandler().send(LeaveDialogRequestMessage())
            err = f"Zaap {self.dstMapId} not in available destinations: {[d.mapId for d in destinations]}"
            return self.on(
                KernelEvent.LeaveDialog,
                lambda e: self.finish(self.DST_ZAAP_NOT_KNOWN, err),
            )

    def onZaapSaved(self, code, err):
        if err:
            Logger().error(f"Save zaap failed for reason: {err}")
        self.finish(True, None)
    
    def onDestMapProcessed(self, event=None):
        KernelEventsManager().send(KernelEvent.ZAAP_TELEPORT)
        if self.bsaveZaap and Kernel().zaapFrame.spawnMapId != PlayedCharacterManager().currentMap.mapId:
            return self.saveZaap(self.onZaapSaved)
        return self.finish(True, None)
