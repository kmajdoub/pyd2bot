import json
import os
from pydofus2.com.ankamagames.dofus.datacenter.world.MapPosition import MapPosition

class TreasureHuntPoiDatabase:
    """Maintains exact same POI database logic as original implementation."""
    
    def __init__(self, hints_file: str, wrong_answers_file: str):
        self.hints_file = hints_file
        self.wrong_answers_file = wrong_answers_file
        
        # Load exactly as before
        with open(self.hints_file, "r") as fp:
            self.hint_db = json.load(fp)

        with open(self.wrong_answers_file, "r") as fp:
            json_content = json.load(fp)
            self.wrong_answers = set([tuple(_) for _ in json_content["recordedWrongAnswers"]])

    def save_hints(self):
        """Save hints exactly as original implementation."""
        with open(self.hints_file, "w") as fp:
            json.dump(self.hint_db, fp, indent=2)

    def save_wrong_answers(self):
        """Save wrong answers exactly as original implementation."""
        with open(self.wrong_answers_file, "w") as fp:
            json.dump({"recordedWrongAnswers": list(self.wrong_answers)}, fp, indent=4)

    def memorize_hint(self, mapId, poiId):
        """Exact same logic as original memorizeHint."""
        mp = MapPosition.getMapPositionById(mapId)
        if str(mp.worldMap) not in self.hint_db:
            self.hint_db[str(mp.worldMap)] = {}
        worldHints = self.hint_db[str(mp.worldMap)]
        if str(mp.id) not in worldHints:
            self.hint_db[str(mp.worldMap)][str(mp.id)] = []
        self.hint_db[str(mp.worldMap)][str(mp.id)].append(poiId)
        self.save_hints()

    def remove_poi_from_map(self, mapId, poiId):
        """Exact same logic as original removePoiFromMap."""
        mp = MapPosition.getMapPositionById(mapId)
        if str(mp.worldMap) not in self.hint_db:
            return
        worldHints = self.hint_db[str(mp.worldMap)]
        if str(mp.id) not in worldHints:
            return
        mapHints = [_ for _ in worldHints[str(mp.id)] if _ != poiId]
        self.hint_db[str(mp.worldMap)][str(mp.id)] = mapHints
        self.save_hints()

    def is_poi_in_map(self, mapId, poiId):
        """Exact same logic as original isPoiInMap."""
        mp = MapPosition.getMapPositionById(mapId)
        if str(mp.worldMap) not in self.hint_db:
            return False
        worldHints = self.hint_db[str(mp.worldMap)]
        if str(mp.id) not in worldHints:
            return False
        mapHints: list = worldHints[str(mp.id)]
        return poiId in mapHints
    
    def add_wrong_answer(self, answer):
        """
        Add a wrong answer to the database and save it immediately.
        
        Args:
            answer: Tuple of (startMapId, poiLabel, currentMapId)
        """
        self.wrong_answers.add(answer)
        with open(self.wrong_answers_file, "w") as fp:
            json.dump({"recordedWrongAnswers": list(self.wrong_answers)}, fp, indent=4)