from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.MapMove import MapMove
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.datacenter.jobs.Skill import Skill
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.InteractiveElementData import \
    InteractiveElementData
from pydofus2.com.ankamagames.dofus.network.messages.game.interactive.InteractiveElementUpdatedMessage import \
    InteractiveElementUpdatedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.interactive.InteractiveUseRequestMessage import \
    InteractiveUseRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.interactive.skill.InteractiveUseWithParamRequestMessage import \
    InteractiveUseWithParamRequestMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger



class UseSkill(AbstractBehavior):
    ELEM_TAKEN = 9801
    ELEM_BEING_USED = 9802
    ELEM_UPDATE_TIMEOUT = 66987
    NO_ENABLED_SKILLS = 668889
    UNREACHABLE_IE = 669874
    TIMEOUT = 9803
    CANT_USE = 9804
    USE_ERROR = 9805
    MAX_TIMEOUTS = 20
    REQ_TIMEOUT = 7

    def __init__(self) -> None:
        super().__init__()
        self.timeoutsCount = 0
        self.ie = None
        self.useErrorListener = None
        self._curr_skill_mp = None
        self._reach_skill_cell_fails = 0
        self._move_to_skill_cell_landingcell = None
        self._cells_blacklist = []
        self._wanted_player_stop = False
        self._stop_code = None
        self._stop_message = None

    def run(
        self,
        ie: InteractiveElementData = None,
        cell=None,
        exactDestination=False,
        waitForSkillUsed=True,
        elementId=None,
        skilluid=None,
    ):
        if ie is None:
            if elementId and skilluid:
                def onIeFound(ie: InteractiveElementData):
                    self.targetIe = ie
                    self.skillUID = ie.skillUID
                    self.elementId = ie.element.elementId
                    self.elementPosition = ie.position
                    self.element = ie.element
                    self.skillId = ie.skillId
                    self.cell = cell
                    self.exactDestination = exactDestination
                    self.waitForSkillUsed = waitForSkillUsed
                    self._useSkill()
                return self.getInteractiveElement(elementId, skilluid, onIeFound)
            else:
                return self.finish(False, "No interactive element provided")
        self.targetIe: InteractiveElementData = ie
        self.skillUID = ie.skillUID
        self.skillId = ie.skillId
        self.elementId = ie.element.elementId
        self.elementPosition = ie.position
        self.element = ie.element
        self.cell = cell
        self.exactDestination = exactDestination
        self.waitForSkillUsed = waitForSkillUsed
        self._useSkill()
        
    def onUseSkillCellReached(self, code, err, landingCell):
        if err:
            if code == MapMove.PLAYER_STOPPED:
                if self._wanted_player_stop:
                    return self.finish(self._stop_code, self._stop_message)
            return self.finish(code, err)
        self._move_to_skill_cell_landingcell = landingCell
        self.requestActivateSkill()
        
    def _useSkill(self) -> None:
        if self.targetIe.element.enabledSkills:
            skillId = self.targetIe.element.enabledSkills[0].skillId
            skill = Skill.getSkillById(skillId)
            Logger().debug(f"Using {skill.name}, range {skill.range}, id {skill.id}")
            if skill.id in [211, 184] :
                self._curr_skill_mp, _ = Kernel().interactiveFrame.getNearestCellToIe(self.element, self.elementPosition)
            if not self._curr_skill_mp:
                self._curr_skill_mp = self.elementPosition
            if self.waitForSkillUsed:
                self.on(KernelEvent.IElemBeingUsed, self.onUsingInteractive,)
                self.on(KernelEvent.InteractiveElementUsed, self.onUsedInteractive)
            self.map_move_to_cell(destCell=self._curr_skill_mp.cellId, exact_destination=False, callback=self.onUseSkillCellReached)
        else:
            self.finish(self.NO_ENABLED_SKILLS, f"Interactive element has no enabled skills!")

    def onUsingInteractive(self, event, entityId, usingElementId):
        if self.elementId == usingElementId:
            if entityId != PlayedCharacterManager().id:
                if MapMove.getInstance():
                    self._stop_message = "Someone else is using this element while we are moving to it!"
                    Logger().warning(self._stop_message)
                    self._wanted_player_stop = True
                    self._stop_code = self.ELEM_BEING_USED
                    MapMove.getInstance().stop()
                else:
                    self.finish(self.ELEM_BEING_USED, "Someone else is using this element")
            elif MapMove.getInstance():
                Logger().debug(f"/!\ Impossible thing happened : Player is using the element, while we are moving to it!!")
                    
    def onUsedInteractive(self, event, entityId, usedElementId):
        if self.elementId == usedElementId:
            if entityId != PlayedCharacterManager().id:
                if self.elementId in Kernel().interactiveFrame._statedElm:
                    if MapMove.getInstance():
                        self._wanted_player_stop = True
                        self._stop_code = self.ELEM_TAKEN
                        self._stop_message = "Someone else is using this element while we are moving to it!"
                        Logger().warning(self._stop_message)
                        MapMove.getInstance().stop()
            else:            
                if self.useErrorListener:
                    self.useErrorListener.delete()
                if self.elementId in Kernel().interactiveFrame._statedElm:
                    if self.targetIe.element.enabledSkills[0].skillId not in [114]:
                        self.once(
                            KernelEvent.InteractiveElemUpdate,
                            self.onInteractiveUpdated,
                            timeout=10,
                            ontimeout=self.onElemUpdateWaitTimeout,
                        )
                else:
                    self.finish(0)

    def onInteractiveUpdated(self, event, msg: InteractiveElementUpdatedMessage):
        if msg.interactiveElement.elementId == self.elementId:
            for skill in msg.interactiveElement.disabledSkills:
                if skill.skillInstanceUid == self.skillUID:
                    self.finish(0)

    def onElemUpdateWaitTimeout(self, listener: Listener):
        if not self.running.is_set():
            return
        self.finish(self.ELEM_UPDATE_TIMEOUT, "Elem update wait timedout")

    def onMapDataRefreshedAfterUseError(self, code, err, elementId):
        if err:
            self.finish(code, err)
        if self._move_to_skill_cell_landingcell.cellId != PlayedCharacterManager().playerMapPoint.cellId:
            self._cells_blacklist.append(self._move_to_skill_cell_landingcell.cellId)
            self._reach_skill_cell_fails += 1
            Logger().warning(f"Player movement to use kill cell didn't actually get executed by server")
            if self._reach_skill_cell_fails > 3:
                return self.finish(self.USE_ERROR, f"Use Error for element {elementId} - Server refuses to move player to skill cell")
            Logger().debug(f"retrying for {self._reach_skill_cell_fails} time")
            return self.map_move_to_cell(destCell=self._curr_skill_mp.cellId, exact_destination=False, callback=self.onUseSkillCellReached, cellsblacklist=self._cells_blacklist)
        self.finish(self.USE_ERROR, f"Use Error for element {elementId}!")
        
    def onUseError(self, event, elementId):
        if not self.running.is_set():
            return
        if MapMove.getInstance():
            MapMove.getInstance().stop()
        Logger().error(f"Use Error for element {elementId}")
        self.requestMapData(callback=lambda code, err: self.onMapDataRefreshedAfterUseError(code, err, elementId))

    def requestActivateSkill(self) -> None:
        if self.waitForSkillUsed:
            self.timeoutsCount = 0
            self.useErrorListener = self.once(
                KernelEvent.InteractiveUseError,
                self.onUseError,
                timeout=self.REQ_TIMEOUT,
                ontimeout=lambda _: self.finish(self.TIMEOUT, "Request timed out"),
                retry_action=self.sendRequestSkill,
                retry_nbr=self.MAX_TIMEOUTS,
            )
            self.currentRequestedElementId = self.elementId
        self.sendRequestSkill()
        if not self.waitForSkillUsed:
            BenchmarkTimer(0.75, lambda: self.finish(0)).start()

    def sendRequestSkill(self, additionalParam=0):
        if additionalParam == 0:
            msg = InteractiveUseRequestMessage()
            msg.init(int(self.elementId), int(self.skillUID))
            ConnectionsHandler().send(msg)
        else:
            msg = InteractiveUseWithParamRequestMessage()
            msg.init(int(self.elementId), int(self.skillUID), int(additionalParam))
            ConnectionsHandler().send(msg)
        InactivityManager().activity()

    def getInteractiveElement(self, elementId, skilluid, callback) -> InteractiveElementData:
        if Kernel().interactiveFrame is None:
            Logger().warning("No roleplay interactive frame found, waiting for it to get pushed")
            return self.once_frame_pushed(
                "RoleplayInteractivesFrame",
                self.getInteractiveElement,
                [elementId, skilluid, callback],
            )
        callback(Kernel().interactiveFrame.getInteractiveElement(elementId, skilluid))
