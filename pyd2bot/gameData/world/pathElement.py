from .mapPoint import MapPoint


class PathElement:

    def __init__(self, mp:MapPoint, orientation:int): 
        if mp is None:
            self.step = MapPoint()
        else:
            self.step = mp
        self.orientation = orientation
        self.cellId = self.step.cellID
        
    def __str__(self) -> str:
        return "PE(cellId: {}, orientation: {})".format(self.cellId, self.orientation)
    