from pyd2bot.farmPaths.CustomRandomFarmPath import CustomRandomFarmPath
from pyd2bot.farmPaths.RandomAreaFarmPath import RandomAreaFarmPath
from pyd2bot.farmPaths.RandomSubAreaFarmPath import \
    RandomSubAreaFarmPath

from pyd2bot.data.enums import PathTypeEnum
from typing import TYPE_CHECKING

from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldGraph import WorldGraph

if TYPE_CHECKING:
    from pyd2bot.data.models import Path

class PathFactory:

    @classmethod
    def from_dto(cls, obj: 'Path'):
        from pyd2bot.data.models import Path

        if not isinstance(obj, Path):
            raise ValueError("session.path must be a Path instance, not " + str(type(obj)))
            
        if obj.type == PathTypeEnum.RandomSubAreaFarmPath:
            return RandomSubAreaFarmPath(
                name=obj.id,
                startVertex=WorldGraph().getVertex(obj.startMapId, obj.startZoneId),
                allowedTransitions=obj.allowedTransitions,
            )
            
        if obj.type == PathTypeEnum.RandomAreaFarmPath:
            return RandomAreaFarmPath(
                name=obj.id,
                startVertex=WorldGraph().getVertex(obj.startMapId, obj.startZoneId)
            )
            
        if obj.type == PathTypeEnum.CustomRandomFarmPath:
            return CustomRandomFarmPath(
                name=obj.id,
                mapIds=obj.mapIds,
            )
        raise ValueError("Unknown path type: " + str(obj.type))
