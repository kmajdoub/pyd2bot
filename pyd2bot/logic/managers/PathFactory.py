from pyd2bot.models.farmPaths.RandomSubAreaFarmPath import RandomSubAreaFarmPath
from pyd2bot.thriftServer.pyd2botService.ttypes import PathType, Path


class PathFactory:
    _pathClass = {
        PathType.RandomSubAreaFarmPath: RandomSubAreaFarmPath,
    }

    @classmethod
    def from_thriftObj(cls, obj: Path):
        pathCls = cls._pathClass.get(obj.type)
        if pathCls:
            return pathCls.from_thriftObj(obj)
        raise Exception("Unknown path type: " + str(obj.type))
