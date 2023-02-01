import threading


class Watcher(threading.Thread):
    
    _runningWatchers = []
    
    def __init__(self, target=None, args=()) -> None:
        super().__init__(target=target, args=args)
        self.name = threading.current_thread().name
    
    @classmethod
    def clear(cls) -> None:
        cls._runningWatchers.clear()
    
    def run(self) -> None:
        Watcher._runningWatchers.append(self)
        super().run()
        Watcher._runningWatchers.remove(self)