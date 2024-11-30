from enum import Enum
from typing import Iterable, Optional

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
    dst_mapId: Optional[int]
    transition: Optional[Transition]
    transition_type: TransitionTypeEnum
    edge: Optional[Edge]
    _transitions: Iterable[Transition]
    _tr_fails_details: dict[Transition, str]

    class errors(Enum):
        INVALID_TRANSITION = 1342
        NEED_QUEST = 879908
        LANDED_ON_WRONG_MAP = 1002

    TRANSITION_PREFERENCES = {
        TransitionTypeEnum.MAP_ACTION: 1,      # Highest priority - basic map change
        TransitionTypeEnum.SCROLL: 2,          # Walking between maps
        TransitionTypeEnum.SCROLL_ACTION: 2,   # Same priority as SCROLL
        TransitionTypeEnum.INTERACTIVE: 3,     # Interactive elements
        TransitionTypeEnum.ITEM_TELEPORT: 6,   # Recall potions
        TransitionTypeEnum.NPC_TRAVEL: 4,      # NPC transportation
        TransitionTypeEnum.ZAAP: 5,            # Zaap transportation
        TransitionTypeEnum.HAVEN_BAG_ZAAP: 7,  # Lowest priority - haven bag
    }

    def __init__(self) -> None:
        super().__init__()
        self.dst_mapId = None
        self.transition = None
        self.transition_type = None
        self.edge = None
        self._transitions = None
        self._tr_fails_details = {}

    def run(self, transition: Transition = None, edge: Edge = None, dstMapId=None):
        if not (edge or transition):
            return self.finish(1, "No transition or edge provided!")
        
        if transition and not dstMapId:
            return self.finish(1, "dstMapId must be provided when you only give a transition to follow!")

        if (edge and edge.dst == PlayedCharacterManager().currVertex) or (
            not edge and dstMapId == PlayedCharacterManager().currentMap.mapId
        ):
            Logger().warning("calling change map with an edge that leads to current player exact position!")
            return self.finish(0)
        
        self.on(KernelEvent.ServerTextInfo, self.onServerTextInfo)

        if transition:
            self.dst_mapId = dstMapId
            self.transition = transition
            
        elif edge:
            self.dst_mapId = edge.dst.mapId
            self.edge = edge
        
        self.followTransition()

    def onServerTextInfo(self, event, msgId, msgType, textId, text, params):
        if textId == 4908:
            Logger().error("Need a quest to be completed")
            return self.finish(self.errors.NEED_QUEST, "Need a quest to be completed")

    @property
    def transitions(self):
        if not self._transitions:
            self._transitions = self.transitionsGen()
        return self._transitions

    def transitionsGen(self) -> Iterable[Transition]:
        if not self.edge and not self.transition:
            return iter([])

        transitions_to_check = [self.transition] if not self.edge else self.edge.transitions
        valid_transitions = [tr for tr in transitions_to_check if tr.isValid]
        
        if not valid_transitions:
            Logger().warning("No valid transitions found!")
            return iter([])

        # Sort transitions based on preference map
        sorted_transitions = sorted(
            valid_transitions,
            key=lambda tr: self.TRANSITION_PREFERENCES.get(TransitionTypeEnum(tr.type), 999)
        )

        return iter(sorted_transitions)

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
            return self.stop(True)

        try:
            self.transition: Transition = next(self.transitions)
        except StopIteration:
            return self.finish(
                self.errors.INVALID_TRANSITION,
                "No valid transition found!, checked transitions results: " + str(self._tr_fails_details),
            )
    
        if not self.transition.isValid:
            return self.finish(self.errors.INVALID_TRANSITION, "Trying to follow a non valid transition!", self.transition)

        self.transition_type = TransitionTypeEnum(self.transition.type)

        Logger().info(f"{self.transition_type.name} map change to {self.dst_mapId}")

        if self.transition_type == TransitionTypeEnum.INTERACTIVE:
            self.interactive_map_change(
                self.dst_mapId,
                self.transition.ieElemId,
                self.transition.skillId,
                self.transition.cell,
                callback=self.onTransitionExecFinished,
            )

        elif self.transition_type in [TransitionTypeEnum.SCROLL, TransitionTypeEnum.SCROLL_ACTION]:
            self.scroll_map_change(
                self.dst_mapId,
                self.transition.transitionMapId,
                self.transition.cell,
                self.transition.direction,
                callback=self.onTransitionExecFinished
            )

        elif self.transition_type == TransitionTypeEnum.MAP_ACTION:
            self.action_map_change(self.dst_mapId, self.transition.cell, callback=self.onTransitionExecFinished)

        elif self.transition_type == TransitionTypeEnum.NPC_TRAVEL:
            self.travel_with_npc(self.transition._npc_travel_infos, callback=self.onTransitionExecFinished)

        elif self.transition_type == TransitionTypeEnum.ZAAP:
            self.useZaap(self.dst_mapId, callback=self.onTransitionExecFinished)

        elif self.transition_type == TransitionTypeEnum.HAVEN_BAG_ZAAP:
            self.teleport_using_havenbag(self.dst_mapId, callback=self.onTransitionExecFinished)

        elif self.transition_type == TransitionTypeEnum.ITEM_TELEPORT and self.transition.itemGID == DataEnum.RAPPEL_POTION_GUID:
            self.use_rappel_potion(callback=self.onTransitionExecFinished)

        else:
            Logger().warning(f"Unsupported transition type {self.transition_type.name}")
            self.followTransition()
