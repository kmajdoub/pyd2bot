import threading
from enum import Enum

from pyd2bot.logic.roleplay.behaviors.BehaviorApi import BehaviorApi
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton

RLOCK = threading.RLock()

class AbstractBehaviorState(Enum):
    UNKNOWN = 0
    RUNNING = 1
    IDLE = 2
    
class AbstractBehavior(BehaviorApi, metaclass=Singleton):
    ALREADY_RUNNING = 666
    _onEmptyCallbacks = dict[str, list[callable]]()
    
    def __init__(self) -> None:
        self.running = threading.Event()
        self.callback = None
        self.endListeners = []
        self.children = list[AbstractBehavior]()
        self.state = AbstractBehaviorState.UNKNOWN
        self.parent = None
        super().__init__()

    def start(self, *args, parent: 'AbstractBehavior'=None, callback=None, **kwargs) -> None:
        if self.parent and not self.parent.running.is_set():
            return Logger().debug(f"Cancel start for reason : parent behavior died.")
        self.callback = callback
        self.parent = parent
        if self.parent:
            self.parent.children.append(self)
        if self.running.is_set():
            error = f"{type(self).__name__} already running by parent {self.parent}."
            if self.callback:
                self.callback(self.ALREADY_RUNNING, error)
            else:
                Logger().error(error)
            return
        self.running.set()
        self.run(*args, **kwargs)
        
    def run(self, *args, **kwargs):
        raise NotImplementedError()

    def onFinish(self, callback):
        self.endListeners.append(callback)

    def finish(self, code: bool, error: str = None, *args, **kwargs) -> None:
        if not self.running.is_set():
            return Logger().warning(f"[{type(self).__name__}] wants to finish but not running!")
        KernelEventsManager().clearAllByOrigin(self)
        from pyd2bot.misc.BotEventsmanager import BotEventsManager
        BotEventsManager().clearAllByOrigin(self)
        callback = self.callback
        self.callback = None
        self.running.clear()
        type(self).clear()
        Logger().info(f"[{type(self).__name__}] Finished.")
        if self.parent and self in self.parent.children:
            self.parent.children.remove(self)
        error = f"[{type(self).__name__}] failed for reason : {error}" if error else None
        if callback is not None:
            callback(code, error, *args, **kwargs)
        else:
            Logger().debug(error)
        while self.endListeners:
            callback = self.endListeners.pop()
            callback(code, error, *args, **kwargs)
        with RLOCK:
            thname = threading.current_thread().name
            if not AbstractBehavior.hasRunning(thname):
                if thname in AbstractBehavior._onEmptyCallbacks:
                    while AbstractBehavior._onEmptyCallbacks[thname]:
                        callback = AbstractBehavior._onEmptyCallbacks[thname].pop()
                        callback(code, error, *args, **kwargs)
                    del AbstractBehavior._onEmptyCallbacks[thname]
            
    @property
    def listeners(self) -> list[Listener]:
        from pyd2bot.misc.BotEventsmanager import BotEventsManager
        return KernelEventsManager().getListenersByOrigin(self) + BotEventsManager().getListenersByOrigin(self)

    def isRunning(self):
        return self.running.is_set()
    
    def getState(self):
        return AbstractBehaviorState.RUNNING.name if self.isRunning() else AbstractBehaviorState.IDLE.name

    @classmethod
    def hasRunning(clsn, name):
        for behavior in AbstractBehavior.getSubs(name):
            if behavior.isRunning():
                return True
    
    @classmethod
    def getRunning(cls) -> list['AbstractBehavior']:
        result = []
        for behavior in AbstractBehavior.getSubs():
            if not behavior.parent and behavior.isRunning():
                result.append(behavior)
        return result

    @classmethod
    def getOtherRunning(cls) -> list['AbstractBehavior']:
        result = []
        for behavior in AbstractBehavior.getSubs():
            if not behavior.parent and type(behavior).__name__ != cls.__name__ and behavior.isRunning():
                result.append(behavior)
        return result

    @staticmethod
    def onFinishAll(callback):
        thname = threading.current_thread().name
        if thname not in AbstractBehavior._onEmptyCallbacks:
            AbstractBehavior._onEmptyCallbacks[thname] = []
        AbstractBehavior._onEmptyCallbacks[thname].append(callback)
    
    def getTreeStr(self, level=0):
        indent = '  ' * level
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
    
    def stop(self):
        # Logger().debug(f"Stopping {type(self).__name__} ...")
        self.finish(True, None)
        # Logger().debug(f"{type(self).__name__} has {len(self.children)} children")
        self.stopChilds()
    
    def stopChilds(self):
        while self.children:
            child = self.children.pop()
            child.stop()
