

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class Test(AbstractBehavior):

    def __init__(self) -> None:
        super().__init__()
        self.requestTimer = None

    def run(self) -> bool:
        def onMapMoveFinished(code, err, landingcell):
            Logger().info(f"Map move finished with code {code} and error {err} and landingcell {landingcell}")
            self.finish(code, err)
        self.mapMove(99, exactDestination=True, callback=onMapMoveFinished)
