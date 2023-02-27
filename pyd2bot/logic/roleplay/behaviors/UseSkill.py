from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.MapMove import MapMove
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import \
    InteractiveElementData
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayWorldFrame import \
    RoleplayWorldFrame
from pydofus2.com.ankamagames.dofus.network.messages.game.interactive.InteractiveUseRequestMessage import \
    InteractiveUseRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.interactive.skill.InteractiveUseWithParamRequestMessage import \
    InteractiveUseWithParamRequestMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class UseSkill(AbstractBehavior):
    
    def __init__(self) -> None:
        super().__init__()
        self.requestTimer = None
        self.ie = None
        
    @property
    def worldFrame(self) -> "RoleplayWorldFrame":
        return Kernel().worker.getFrameByName("RoleplayWorldFrame")
    
    def start(self, ie: InteractiveElementData, callback, cell=None, exactDistination=True):
        if self.running.is_set():
            return callback(False, f"Already using skill {self.ie}!")
        self.running.set()
        self.targetIe = ie
        self.skillUID = ie.skillUID
        self.elementId = ie.element.elementId
        self.elementPosition = ie.position
        self.element = ie.element
        self.cell = cell
        self.callback = callback
        self.exactDistination = exactDistination
        self.useSkill()

    def useSkill(self) -> None:
        sendInteractiveUseRequest = True
        cell = self.cell
        if not cell:
            cell, sendInteractiveUseRequest = self.worldFrame.getNearestCellToIe(self.element, self.elementPosition)
        if not sendInteractiveUseRequest:
            return self.finish(False, "Can't use this interactive element")
        def onmoved(errType, error):
            if error:
                return self.finish(errType, error)
            self.requestActivateSkill()
        KernelEventsManager().on(KernelEvent.INTERACTIVE_ELEMENT_BEING_USED, self.onUsingInteractive)
        KernelEventsManager().on(KernelEvent.INTERACTIVE_ELEMENT_USED, self.onUsingInteractive)
        MapMove().start(cell, onmoved, self.exactDistination)
        
    def ontimeout(self):
        self.requestTimer = None
        self.finish(False, "Request timed out")
    
    def onUsingInteractive(self, event, entityId, usingElementId):
        if self.elementId == usingElementId:
            self.tearDown()
            if entityId != PlayedCharacterManager().id:
                self.finish(False, "Someone else is using this element")
                
    def onUsedInteractive(self, event, entityId, usedElementId):
        if self.elementId == usedElementId:                    
            self.tearDown()
            if entityId != PlayedCharacterManager().id:
                self.finish(False, "Someone else used this element")
            else:
                self.finish(True)
    
    def onUseError(self, event, elementId):
        self.tearDown()
        self.finish(False, "Can't use this element, probably not in range")
    
    def tearDown(self):
        if self.requestTimer:
            self.requestTimer.cancel()
        if MapMove().isRunning():
            MapMove().stop()
        KernelEventsManager().remove_listener(KernelEvent.INTERACTIVE_USE_ERROR, self.onUseError)
        KernelEventsManager().remove_listener(KernelEvent.INTERACTIVE_ELEMENT_BEING_USED, self.onUsingInteractive)
        KernelEventsManager().remove_listener(KernelEvent.INTERACTIVE_ELEMENT_USED, self.onUsingInteractive)
        
    def requestActivateSkill(self, additionalParam=0) -> None:
        KernelEventsManager().once(KernelEvent.INTERACTIVE_USE_ERROR, self.onUseError)
        self.requestTimer = BenchmarkTimer(7, self.ontimeout)
        self.requestTimer.start()
        self.currentRequestedElementId = self.elementId
        if additionalParam == 0:
            iurmsg = InteractiveUseRequestMessage()
            iurmsg.init(int(self.elementId), int(self.skillUID))
            ConnectionsHandler().send(iurmsg)
        else:
            iuwprmsg = InteractiveUseWithParamRequestMessage()
            iuwprmsg.init(int(self.elementId), int(self.skillUID), int(additionalParam))
            ConnectionsHandler().send(iuwprmsg)
        self.canMove = False