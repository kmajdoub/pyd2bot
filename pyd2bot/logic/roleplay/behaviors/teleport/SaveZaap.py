from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
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


class SaveZaap(AbstractBehavior):
    ZAAP_IE_NOTFOUND = 255555
    
    def __init__(self) -> None:
        super().__init__()

    def run(self) -> bool:
        if int(Kernel().zaapFrame.spawnMapId) == int(PlayedCharacterManager().currentMap.mapId):
            Logger().debug(f"Zaap already saved in current map {PlayedCharacterManager().currentMap.mapId}.")
            return self.finish(True, None)
        if Kernel().interactiveFrame:
            self.openCurrMapZaapDialog()
        else:
            self.onceFramePushed("RoleplayInteractivesFrame", self.openCurrMapZaapDialog)

    def openCurrMapZaapDialog(self):
        self.zaapIe = Kernel().interactiveFrame.getZaapIe()
        if not self.zaapIe:
            return self.finish(self.ZAAP_IE_NOTFOUND, "Zaap ie not found in current Map")
        self.once(
            event_id=KernelEvent.TeleportDestinationList,
            callback=self.onTeleportDestinationList,
        )
        self.useSkill(ie=self.zaapIe, waitForSkillUsed=False, callback=self.onZaapSkillUsed)
        
    def onZaapSkillUsed(self, code, err):
        if err:
            return self.finish(code, err)

    def onZaapSaveResp(self, event_id, destinations: list[TeleportDestinationWrapper], ttype):
        ConnectionsHandler().send(LeaveDialogRequestMessage())
        return self.on(
            KernelEvent.LeaveDialog,
            lambda _: self.finish(True, None),
        )
        
    def onTeleportDestinationList(self, event_id, destinations: list[TeleportDestinationWrapper], ttype):
        Logger().debug(f"Zaap teleport destinations received.")
        Kernel().zaapFrame.zaapRespawnSaveRequest()
        return self.once(
            KernelEvent.TeleportDestinationList,
            self.onZaapSaveResp,
        )
