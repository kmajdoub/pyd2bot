import threading
from enum import Enum

from pyd2bot.logic.roleplay.behaviors.BehaviorApi import BehaviorApi
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.metaclass.Singleton import Singleton

RLOCK = threading.RLock()


class AbstractBehaviorState(Enum):
    UNKNOWN = 0
    RUNNING = 1
    IDLE = 2


class AbstractBehavior(BehaviorApi, metaclass=Singleton):
    IS_BACKGROUND_TASK = False
    ALREADY_RUNNING = 666
    STOPPED = 988273

    def __init__(self) -> None:
        self.running = threading.Event()
        self.callback = None
        self.endListeners = []
        self.children = list[AbstractBehavior]()
        self.state = AbstractBehaviorState.UNKNOWN
        self.parent = None
        super().__init__()

    def start(self, *args, parent: "AbstractBehavior" = None, callback=None, **kwargs) -> None:
        if self.parent and not self.parent.running.is_set():
            Logger().debug(f"Cancel start for reason : parent {self.parent} behavior died.")
            return
        KernelEventsManager().send(KernelEvent.ClientStatusUpdate, f"STARTING_{type(self).__name__.upper()}")
        self.callback = callback
        self.parent = parent
        if self.parent:
            self.parent.children.append(self)
        if self.running.is_set():
            error = f"{type(self).__name__} already running by parent {self.parent}."
            KernelEventsManager().send(
                KernelEvent.ClientStatusUpdate,
                f"ERROR_{type(self).__name__.upper()}",
                {"error": error, "code": self.ALREADY_RUNNING},
            )
            if self.callback:
                Kernel().defer(lambda: self.callback(self.ALREADY_RUNNING, error))
            else:
                Logger().error(error)
            return
        self.running.set()
        self.run(*args, **kwargs)

    def run(self, *args, **kwargs):
        raise NotImplementedError()

    def finish(self, code: bool, error: str = None, *args, **kwargs) -> None:
        if not self.running.is_set():
            return Logger().warning(f"[{type(self).__name__}] wants to finish but not running!")
        KernelEventsManager().clear_all_by_origin(self)
        from pyd2bot.misc.BotEventsManager import BotEventsManager

        BotEventsManager().clear_all_by_origin(self)
        callback = self.callback
        self.callback = None
        self.running.clear()
        type(self).clear()
        # Logger().info(f"[{type(self).__name__}] Finished.")
    
        if self.parent and self in self.parent.children:
            self.parent.children.remove(self)

        error = f"[{type(self).__name__}] failed for reason : {error}" if error else None
        if callback is not None:
            Kernel().defer(lambda: callback(code, error, *args, **kwargs))
        else:
            Logger().debug(f"[{type(self).__name__}] Finished with result :: [{code}] - {error}")
        if error:
            KernelEventsManager().send(
                KernelEvent.ClientStatusUpdate,
                f"ERROR_{type(self).__name__.upper()}",
                {"error": error, "code": str(code)},
            )
        else:
            KernelEventsManager().send(KernelEvent.ClientStatusUpdate, f"FINISHED_{type(self).__name__.upper()}")

    @property
    def listeners(self) -> list[Listener]:
        from pyd2bot.misc.BotEventsManager import BotEventsManager

        return KernelEventsManager().get_listeners_by_origin(self) + BotEventsManager().get_listeners_by_origin(self)

    def isRunning(self):
        return self.running.is_set()

    def getState(self):
        return AbstractBehaviorState.RUNNING.name if self.isRunning() else AbstractBehaviorState.IDLE.name

    @classmethod
    def hasRunning(cls, name):
        for behavior in AbstractBehavior.getSubs(name):
            if behavior.isRunning():
                return True

    @classmethod
    def getRunning(cls) -> list["AbstractBehavior"]:
        result = []
        for behavior in AbstractBehavior.getSubs():
            if not behavior.parent and behavior.isRunning():
                result.append(behavior)
        return result

    @classmethod
    def getOtherRunningBehaviors(cls) -> list["AbstractBehavior"]:
        result = []
        for behavior in cls.getRunning():
            if type(behavior).__name__ != cls.__name__:
                result.append(behavior)
        return result

    def getTreeStr(self, level=0):
        indent = "  " * level
        result = ""
        if level > 0:
            result = f"{indent}{type(self).__name__}\n"
        for child in self.children:
            result += child.getTreeStr(level + 1)
        return result

    def __str__(self) -> str:
        listeners = [str(listener) for listener in self.listeners]
        result = f"{type(self).__name__} ({self.getState()})"
        if self.listeners:
            result += f", Listeners: {listeners}"
        if self.children:
            result += f", Children: {self.getTreeStr()}"
        return result

    def stop(self, clear_callback=False):
        if clear_callback:
            self.callback = lambda *_: Logger().debug("Callback cleared")
        self.stopChildren(clear_callback)
        self.finish(0)

    def stopChildren(self, clear_callbacks=False):
        while self.children:
            child = self.children.pop()
            child.stop(clear_callbacks)
