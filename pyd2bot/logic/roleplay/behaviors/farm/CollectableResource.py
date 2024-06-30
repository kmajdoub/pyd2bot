
from typing import TYPE_CHECKING, List

from pyd2bot.data.models import JobFilter
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import \
    CollectableElement
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import \
    PathFinding

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
        movePath = PathFinding().findPath(PlayedCharacterManager().entity.position, self.position)
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
            movePath = PathFinding().findPath(playerEntity.position, self.position)
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
        return PlayedCharacterManager().getJobLevel(self.resource.skill.parentJobId) >= self.resource.skill.levelMin

    def isFiltered(self, jobFilters: List[JobFilter]) -> bool:
        for jobFilter in jobFilters:
            if jobFilter.matchesResource(self.jobId, self.resourceId):
                return False
        return True

    @property
    def canCollect(self):
        return self.resource.enabled and self.hasRequiredLevel and self.reachable

    def canFarm(self, jobFilters: List[JobFilter]=None):
        if jobFilters:
            return self.canCollect and not self.isFiltered(jobFilters)
        return self.canCollect

    def farm(self, callback, caller: 'AbstractFarmBehavior'=None):
        caller.useSkill(
            elementId=self.resource.id,
            skilluid=self.resource.interactiveSkill.skillInstanceUid,
            cell=self.nearestCell.cellId,
            callback=callback,
        )

    def __hash__(self) -> int:
        return self.resource.id
