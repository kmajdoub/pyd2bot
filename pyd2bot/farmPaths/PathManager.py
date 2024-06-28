import json
import os

from pyd2bot.data.models import Path
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

__dir__ = os.path.dirname(os.path.abspath(__file__))
default_paths_json_file = os.path.join(__dir__, "paths.json")


class PathManager:
    _paths = dict[str, Path]()
    _data_file = default_paths_json_file

    with open(_data_file, 'r') as fp:
        paths_list = json.load(fp)
        for path in paths_list:
            _paths[path['id']] = Path(**path)
        
    @classmethod
    def get_path(cls, path_name) -> Path:
        if path_name not in cls._paths:
            raise Exception(f"Path {path_name} not found")
        return cls._paths[path_name]