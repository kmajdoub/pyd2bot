
from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import \
    CollectableElement
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import \
    Pathfinding

if TYPE_CHECKING:
    from pyd2bot.logic.roleplay.behaviors.AbstractFarmBehavior import \
        AbstractFarmBehavior

class CollectableResource:
    def __init__(self, it: CollectableElement):
        self.resource = it
        self._nearestCell = None
        self.timeSinceLastTimeCollected = None

    @property
    def uid(self):
        return self.resource.id
    
    @property
    def resourceId(self):
        return self.resource.skill.gatheredRessource.id
    
    @property
    def jobId(self):
        return self.resource.skill.parentJobId
    
    @property
    def reachable(self):
        return self.nearestCell is not None and self.nearestCell.distanceTo(self.position) <= self.resource.skill.range

    @property
    def distance(self):
        movePath = Pathfinding().findPath(PlayedCharacterManager().entity.position, self.position)
        if movePath is None:
            return -1
        return len(movePath.path)

    @property
    def nearestCell(self):
        if not self._nearestCell:
            playerEntity = PlayedCharacterManager().entity
            if playerEntity is None:
                Logger().debug("Player entity not found!")
                self._nearestCell = None
                return None
            movePath = Pathfinding().findPath(playerEntity.position, self.position)
            if movePath is None:
                self._nearestCell = None
                return None
            self._nearestCell = movePath.end
        return self._nearestCell

    @property
    def position(self):
        return MapDisplayManager().getIdentifiedElementPosition(self.resource.id)

    @property
    def hasRequiredLevel(self):
        return PlayedCharacterManager().joblevel(self.resource.skill.parentJobId) >= self.resource.skill.levelMin

    def isFiltered(self, jobFilter):
        jobId = self.resource.skill.parentJobId
        return jobId not in jobFilter or (jobFilter[jobId] and self.resource.skill.gatheredRessource.id not in jobFilter[jobId])

    @property
    def canCollecte(self):
        return self.resource.enabled and self.hasRequiredLevel and self.reachable

    def canFarm(self, jobFilter=None):
        if jobFilter:
            return self.canCollecte and not self.isFiltered(jobFilter)
        return self.canCollecte

    def farm(self, callback, caller: 'AbstractFarmBehavior'=None):
        caller.useSkill(
            elementId=self.resource.id,
            skilluid=self.resource.interactiveSkill.skillInstanceUid,
            cell=self.nearestCell.cellId,
            callback=callback,
        )

    def __hash__(self) -> int:
        return self.resource.id
