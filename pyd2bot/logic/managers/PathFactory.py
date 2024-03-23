from pyd2bot.models.farmPaths.CustomRandomFarmPath import CustomRandomFarmPath
from pyd2bot.models.farmPaths.RandomAreaFarmPath import RandomAreaFarmPath
from pyd2bot.models.farmPaths.RandomSubAreaFarmPath import \
    RandomSubAreaFarmPath
from pyd2bot.models.session.models import Path, PathType


class PathFactory:

    @classmethod
    def from_dto(cls, obj: Path):
        if not isinstance(obj, Path):
            raise ValueError("session.path must be a Path instance, not " + str(type(obj)))
            
        if obj.type == PathType.RandomSubAreaFarmPath:
            return RandomSubAreaFarmPath(
                name=obj.id,
                startVertex=obj.startVertex,
                transitionTypeWhitelist=obj.transitionTypeWhitelist,
            )
            
        if obj.type == PathType.RandomAreaFarmPath:
            return RandomAreaFarmPath(
                name=obj.id,
                startVertex=obj.startVertex,
                
            )
            
        if obj.type == PathType.CustomRandomFarmPath:
            return CustomRandomFarmPath(
                name=obj.id,
                mapIds=obj.mapIds,
            )
        raise ValueError("Unknown path type: " + str(obj.type))
