from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.logic.roleplay.behaviors.teleport.SaveZaap import SaveZaap
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.internalDatacenter.taxi.TeleportDestinationWrapper import \
    TeleportDestinationWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.dialog.LeaveDialogRequestMessage import \
    LeaveDialogRequestMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class UseZaap(AbstractBehavior):
    ZAAP_NOTFOUND = 255898
    DST_ZAAP_NOT_KNOWN = 265574
    NOT_RICH_ENOUGH = 788888
    
    
    def __init__(self) -> None:
        super().__init__()

    def run(self, dstMapId, bsaveZaap=False) -> bool:
        Logger().debug(f"Use zaap to dest {dstMapId} called")
        self.dstMapId = dstMapId
        self.bsaveZaap = bsaveZaap
        if not PlayedCharacterManager().isZaapKnown(dstMapId):
            return self.finish(self.DST_ZAAP_NOT_KNOWN, "Destination zaap is not a known zaap!")
        if Kernel().interactivesFrame:
            self.openCurrMapZaapDialog()
        else:
            self.onceFramePushed("RoleplayInteractivesFrame", self.openCurrMapZaapDialog)

    def openCurrMapZaapDialog(self):
        self.zaapIe = Kernel().interactivesFrame.getZaapIe()
        if not self.zaapIe:
            return self.finish(self.ZAAP_NOTFOUND, "Zaap ie not found in current Map")
        self.once(KernelEvent.TeleportDestinationList, self.onTeleportDestinationList)
        self.useSkill(ie=self.zaapIe, waitForSkillUsed=False, callback=self.onZaapSkillUsed)
        
    def onZaapSkillUsed(self, code, err):
        if err:
            return self.finish(code, err)
        
    def onTeleportDestinationList(self, event_id, destinations: list[TeleportDestinationWrapper], ttype):
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
                return Kernel().zaapFrame.teleportRequest(dst.cost, ttype, dst.destinationType, dst.mapId)
        else:
            ConnectionsHandler().send(LeaveDialogRequestMessage())
            err = f"Didnt find dest zaap {dst.mapId} in teleport destinations, destinations: {[d.mapId for d in destinations]}"
            return self.on(
                KernelEvent.LeaveDialog,
                lambda e: self.finish(self.DST_ZAAP_NOT_KNOWN, err),
            )

    def onZapSaveEnd(self, code, err):
        if err:
            Logger().error(f"Save zaap failed for reason: {err}")
        self.finish(True, None)
    
    def onDestMapProcessed(self, event_id=None):
        if self.bsaveZaap and Kernel().zaapFrame.spawnMapId != PlayedCharacterManager().currentMap.mapId:
            return self.saveZaap(self.onZapSaveEnd)
        return self.finish(True, None)
