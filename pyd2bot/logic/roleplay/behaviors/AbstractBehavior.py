import threading
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton


class AbstractBehavior(metaclass=Singleton):
    
    def __init__(self) -> None:
        self.running = threading.Event()
        self.callback = None
        super().__init__()

    def start(self, *args, **kwargs) -> None:
        raise NotImplementedError("Abstract method.")

    def finish(self, status: bool, error: str = None) -> None:
        if not self.running.is_set():
            return Logger().warning(f"[{type(self).__name__}] wants to finish but not running!")
        Logger().info(f"[{type(self).__name__}] Finished.")
        callback = self.callback
        self.callback = None
        self.running.clear()
        type(self).clear()
        if callback:
            callback(status, error)
    
    def isRunning(self):
        return self.running.is_set()