from typing import Iterable

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import TransitionTypeEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class ChangeMap(AbstractBehavior):
    INVALID_TRANSITION = 1342
    NEED_QUEST = 879908
    LANDED_ON_WRONG_MAP = 1002

    def __init__(self) -> None:
        super().__init__()
        self.dstMapId = None
        self.transition = None
        self.trType = None
        self.edge = None
        self._transitions = None
        self._tr_fails_details = {}

    def run(self, transition: Transition = None, edge: Edge = None, dstMapId=None):
        self.on(KernelEvent.ServerTextInfo, self.onServerTextInfo)
        if transition:
            self.dstMapId = dstMapId
            self.transition = transition
            self.followTransition()
        elif edge:
            self.dstMapId = edge.dst.mapId
            self.edge = edge
            self.followEdge()
        else:
            self.finish(1, "No transition or edge provided")

    def onServerTextInfo(self, event, msgId, msgType, textId, text, params):
        if textId == 4908:
            Logger().error("Need a quest to be completed")
            return self.finish(self.NEED_QUEST, "Need a quest to be completed")

    @property
    def transitions(self):
        if not self._transitions:
            self._transitions = self.transitionsGen()
        return self._transitions

    def transitionsGen(self) -> Iterable[Transition]:
        mapAction_trs = []
        scroll_trs = []
        other_trs = []

        transitions_to_check = [self.transition] if not self.edge else self.edge.transitions
        
        for tr in transitions_to_check:
            if not tr.isValid:
                Logger().warning(f"Skipping non valid transition {tr}!")
                continue
            if TransitionTypeEnum(tr.type) == TransitionTypeEnum.MAP_ACTION:
                mapAction_trs.append(tr)
            elif TransitionTypeEnum(tr.type) in [TransitionTypeEnum.SCROLL, TransitionTypeEnum.SCROLL_ACTION]:
                scroll_trs.append(tr)
            else:
                other_trs.append(tr)
        all_trs = mapAction_trs + scroll_trs + other_trs
        return iter(all_trs)

    def followEdge(self):
        if (self.edge.dst == PlayedCharacterManager().currVertex) or (
            not self.edge and self.dstMapId == PlayedCharacterManager().currentMap.mapId
        ):
            Logger().warning("calling change map with an edge that leads to current player exact vertex!")
            return self.finish(0)

        self.followTransition()

    def onTransitionExecFinished(self, code, error):
        if error:
            Logger().error(f"Transition {self.transition} failed for reason [{code}] : {error}")
            self._tr_fails_details[self.transition] = f"Transition failed for reason [{code}] : {error}"
            return self.followTransition()

        self.finish(0, None, self.transition)

    def followTransition(self):
        if Kernel().worker._terminating.is_set():
            return

        if PlayedCharacterManager().isInFight:
            self.stop(0)
            return

        try:
            self.transition: Transition = next(self.transitions)
        except StopIteration:
            return self.finish(
                self.INVALID_TRANSITION,
                "No valid transition found!, available transitions: " + str(self._tr_fails_details),
            )
    
        if not self.transition.isValid:
            return self.finish(self.INVALID_TRANSITION, "Trying to follow a non valid transition")

        self.trType = TransitionTypeEnum(self.transition.type)

        Logger().info(f"{self.trType.name} map change to {self.dstMapId}")

        if self.trType == TransitionTypeEnum.INTERACTIVE:
            self.interactive_map_change(
                self.dstMapId,
                self.transition.ieElemId,
                self.transition.skillId,
                self.transition.cell,
                callback=self.onTransitionExecFinished,
            )

        elif self.trType in [TransitionTypeEnum.SCROLL, TransitionTypeEnum.SCROLL_ACTION]:
            self.scroll_map_change(
                self.dstMapId,
                self.transition.transitionMapId,
                self.transition.cell,
                self.transition.direction,
                callback=self.onTransitionExecFinished
            )

        elif self.trType == TransitionTypeEnum.MAP_ACTION:
            self.action_map_change(self.dstMapId, self.transition.cell, callback=self.onTransitionExecFinished)

        elif self.trType == TransitionTypeEnum.NPC_TRAVEL:
            self.travel_with_npc(self.transition._npc_travel_infos, callback=self.onTransitionExecFinished)

        elif self.trType == TransitionTypeEnum.ZAAP:
            self.useZaap(self.dstMapId, callback=self.onTransitionExecFinished)

        elif self.trType == TransitionTypeEnum.HAVEN_BAG_ZAAP:
            self.teleport_using_havenbag(self.dstMapId, callback=self.onTransitionExecFinished)

        elif self.trType == TransitionTypeEnum.ITEM_TELEPORT and self.transition.itemGID == DataEnum.RAPPEL_POTION_GUID:
            self.use_rappel_potion(callback=self.onTransitionExecFinished)

        else:
            self.finish(self.INVALID_TRANSITION, f"Unsupported transition type {self.trType.name}")
