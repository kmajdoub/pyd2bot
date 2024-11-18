from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import \
    WorldGraph
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class FindHintNpc(AbstractBehavior):
    UNABLE_TO_FIND_HINT = 475556

    def __init__(self) -> None:
        super().__init__()
        self.npcId = None
        self.direction = None

    def run(self, npcId, direction):
        self.npcId = npcId
        self.direction = direction
        self.on(KernelEvent.TreasureHintInformation, self.onTreasureHintInfos)
        self.onNewMap(True, None)

    def onTreasureHintInfos(self, event, npcId):
        if npcId == self.npcId:
            Logger().debug(f"Hint npc found!!")
            return self.finish(0)

    def onNewMap(self, code, err):
        if err:
            return self.finish(code, err)
        found_thnpc = Kernel().roleplayEntitiesFrame.treasureHuntNpc
        if found_thnpc and found_thnpc.npcId == self.npcId:
            # while parsing new map data if the special treasure hunt npc is found it is stored in the treasureHuntNpc attribute
            # if its found we simply return without ending the behavior because the entities frame it self will send the event treasureHuntNpc that will 
            # be cought in this same behvior.
            # but if its not found then we have to move to another map
            return
        currV = PlayedCharacterManager().currVertex
        for edge in WorldGraph().getOutgoingEdgesFromVertex(currV):
            for transition in edge.transitions:
                if transition.direction != -1 and transition.direction == self.direction:
                    return self.changeMap(transition=transition, dstMapId=edge.dst.mapId, callback=self.onNewMap)
        self.finish(self.UNABLE_TO_FIND_HINT, f"Couldn't find NPC hint in the given direction")
