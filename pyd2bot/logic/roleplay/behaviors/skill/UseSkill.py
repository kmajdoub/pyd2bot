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
        self._reach_skillcell_fails = 0
        self._move_to_skillcell_landingcell = None
        self._cells_blacklist = []
        self._wanted_player_stop = False

    def run(
        self,
        ie: InteractiveElementData = None,
        cell=None,
        exactDistination=False,
        waitForSkillUsed=True,
        elementId=None,
        skilluid=None,
    ):
        if ie is None:
            if elementId and skilluid:
                def onIeFound(ie: InteractiveElementData):
                    self.targetIe: InteractiveElementData = ie
                    self.skillUID = ie.skillUID
                    self.elementId = ie.element.elementId
                    self.elementPosition = ie.position
                    self.element = ie.element
                    self.skillId = ie.skillId
                    self.cell = cell
                    self.exactDistination = exactDistination
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
        self.exactDistination = exactDistination
        self.waitForSkillUsed = waitForSkillUsed
        self._useSkill()
        
    def onUseSkillCellReached(self, code, err, landingCell):
        if err:
            if code == MapMove.PLAYER_STOPED:
                if self._wanted_player_stop:
                    self._wanted_player_stop = False
                    return
            return self.finish(code, err)
        self._move_to_skillcell_landingcell = landingCell
        self.requestActivateSkill()
        
    def _useSkill(self) -> None:
        if self.targetIe.element.enabledSkills:
            skillId = self.targetIe.element.enabledSkills[0].skillId
            skill = Skill.getSkillById(skillId)
            Logger().debug(f"Using {skill.name}, range {skill.range}, id {skill.id}")
            if skill.id in [211, 184] :
                self._curr_skill_mp, send_request = Kernel().interactivesFrame.getNearestCellToIe(self.element, self.elementPosition)
            if not self._curr_skill_mp:
                self._curr_skill_mp = self.elementPosition
            if self.waitForSkillUsed:
                self.on(KernelEvent.IElemBeingUsed, self.onUsingInteractive,)
                self.on(KernelEvent.InteractiveElementUsed, self.onUsedInteractive)
            self.mapMove(destCell=self._curr_skill_mp.cellId, exactDistination=False, callback=self.onUseSkillCellReached)
        else:
            self.finish(self.NO_ENABLED_SKILLS, f"Interactive element has no enabled skills!")

    def onUsingInteractive(self, event, entityId, usingElementId):
        if self.elementId == usingElementId:
            if MapMove().isRunning():
                self._wanted_player_stop = True
                MapMove().stop()
            if entityId != PlayedCharacterManager().id:
                Logger().error(f"Someone else is using this element, while we are moving to it, stopping map move")
                self.finish(self.ELEM_BEING_USED, "Someone else is using this element")

    def onUsedInteractive(self, event, entityId, usedElementId):
        if self.elementId == usedElementId:
            if entityId != PlayedCharacterManager().id:
                if self.elementId in Kernel().interactivesFrame._statedElm:
                    if MapMove().isRunning():
                        self._wanted_player_stop = True
                        MapMove().stop()
                    self.finish(self.ELEM_TAKEN, "Someone else used this element")
            else:            
                if self.useErrorListener:
                    self.useErrorListener.delete()
                if self.elementId in Kernel().interactivesFrame._statedElm:
                    if self.targetIe.element.enabledSkills[0].skillId not in [114]:
                        self.once(
                            KernelEvent.InteractiveElemUpdate,
                            self.onInteractiveUpdated,
                            timeout=10,
                            ontimeout=self.onElemUpdateWaitTimeout,
                        )
                else:
                    self.finish(True, None)

    def onInteractiveUpdated(self, event, ieumsg: InteractiveElementUpdatedMessage):
        if ieumsg.interactiveElement.elementId == self.elementId:
            for skill in ieumsg.interactiveElement.disabledSkills:
                if skill.skillInstanceUid == self.skillUID:
                    self.finish(True, None)

    def onElemUpdateWaitTimeout(self, listener: Listener):
        if not self.running.is_set():
            return
        self.finish(self.ELEM_UPDATE_TIMEOUT, "Elem update wait timedout")

    def onMapDataRefreshedAfterUseError(self, code, err, elementId):
        if err:
            self.finish(code, err)
        if self._move_to_skillcell_landingcell.cellId != PlayedCharacterManager().playerMapPoint.cellId:
            self._cells_blacklist.append(self._move_to_skillcell_landingcell.cellId)
            self._reach_skillcell_fails += 1
            Logger().warning(f"Player movement to useskill cell didn't actually get executed by server")
            if self._reach_skillcell_fails > 5:
                return self.finish(self.USE_ERROR, f"Use Error for element {elementId} - Server refuses to move player to skill cell")
            Logger().debug(f"retrying for {self._reach_skillcell_fails} time")
            return self.mapMove(destCell=self._curr_skill_mp.cellId, exactDistination=False, callback=self.onUseSkillCellReached, cellsblacklist=self._cells_blacklist)
        self.finish(self.USE_ERROR, f"Use Error for element {elementId}!")
        
    def onUseError(self, event, elementId):
        if not self.running.is_set():
            return
        
        if MapMove().isRunning():
            MapMove().stop()
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
                retryAction=self.sendRequestSkill,
                retryNbr=self.MAX_TIMEOUTS,
            )
            self.currentRequestedElementId = self.elementId
        self.sendRequestSkill()
        if not self.waitForSkillUsed:
            self.finish(True, None)

    def sendRequestSkill(self, additionalParam=0):
        if additionalParam == 0:
            iurmsg = InteractiveUseRequestMessage()
            iurmsg.init(int(self.elementId), int(self.skillUID))
            ConnectionsHandler().send(iurmsg)
        else:
            iuwprmsg = InteractiveUseWithParamRequestMessage()
            iuwprmsg.init(int(self.elementId), int(self.skillUID), int(additionalParam))
            ConnectionsHandler().send(iuwprmsg)
        InactivityManager().activity()

    def getInteractiveElement(self, elementId, skilluid, callback) -> InteractiveElementData:
        if Kernel().interactivesFrame is None:
            Logger().warning("No roleplay interactive frame found, waiting for it to get pushed")
            return self.onceFramePushed(
                "RoleplayInteractivesFrame",
                self.getInteractiveElement,
                [elementId, skilluid, callback],
            )
        callback(Kernel().interactivesFrame.getInteractiveElement(elementId, skilluid))
