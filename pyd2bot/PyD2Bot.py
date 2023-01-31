import threading
import time
from pyd2bot.thriftServer.pyd2botServer import Pyd2botServer
from thrift.protocol.THeaderProtocol import THeaderProtocolFactory
from thrift.protocol.TJSONProtocol import TJSONProtocolFactory
import pyd2bot.thriftServer.pyd2botService.Pyd2botService as Pyd2botService
from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton
from thrift.transport import TTransport
from thrift.transport.TSocket import TSocket, TServerSocket
from thrift.protocol import TBinaryProtocol
from thrift.server import THttpServer
from pyd2bot.thriftServer.HttpRequestHandler import getReqHandler


class PyD2Bot(metaclass=Singleton):
    _stop = threading.Event()
    id: str
    _running_threads = list[threading.Thread]()
    _daemon: int
    processor = None
    serverTransport = None
    inputTransportFactory = None
    inputProtocolFactory = None
    
    def __init__(self, id:str, host: str, port: int, deamon=False) -> None:
        self.id = id
        self.host = host
        self.port = port
        self._daemon = deamon
        self.handler = Pyd2botServer(self.id)       
        self.processor = Pyd2botService.Processor(self.handler)
    
    def runHttpServer(self):
        self.serverTransport = THttpServer.THttpServer(self.processor, (self.host, self.port), TJSONProtocolFactory())
        self.serverTransport.httpd.RequestHandlerClass = getReqHandler(self.serverTransport)
        self.Logger().info(f"[Server - {self.id}] Started serving on {self.host}:{self.port}")
        self.serverTransport.serve()
        
    def runSocketServer(self):
        self._stop.clear()
        self.serverTransport = TServerSocket(host=self.host, port=self.port)
        self.Logger().info(f"[Server - {self.id}] Threads started")
        self.serverTransport.listen()
        self.Logger().info(f"[Server - {self.id}] Started listening on {self.host}:{self.port}")
        while not self._stop.is_set():
            try:
                client: TSocket = self.serverTransport.accept()
                if not client:
                    continue
                t = threading.Thread(target=self.serveClient, args=(client,))
                t.setDaemon(self._daemon)
                t.start()
                self._running_threads.append(t)
                self.Logger().info(f"[Server - {self.id}] Accepted client: {client}")
            except Exception as x:
                self.logger.exception(x)
        self.Logger().info(f"[Server - {self.id}] Goodbye crual world!")

    def runClient(self, host: str, port: int):
        transport = TSocket(host, port)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = Pyd2botService.Client(protocol)
        for k in range(5):
            try:
                transport.open()
                return transport, client
            except Exception as x:
                self.logger.exception(x)
                time.sleep(5)
                continue
        raise Exception("Can't connect to server")
        
    def serveClient(self, client: TSocket):
        itrans = self.inputTransportFactory.getTransport(client)
        iprot = self.inputProtocolFactory.getProtocol(itrans)
        if isinstance(self.inputProtocolFactory, THeaderProtocolFactory):
            otrans = None
            oprot = iprot
        else:
            otrans = self.outputTransportFactory.getTransport(client)
            oprot = self.outputProtocolFactory.getProtocol(otrans)
        try:
            while not self._stop.is_set():
                self.processor.process(iprot, oprot)
        except TTransport.TTransportException:
            pass
        except Exception as x:
            self.logger.exception(x)
        itrans.close()
        if otrans:
            otrans.close()
        client.close()
            
    def stopServer(self):
        self.Logger().info(f"[Server - {self.id}] Stop called")
        self._stop.set()