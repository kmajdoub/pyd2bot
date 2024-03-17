from six.moves import BaseHTTPServer
from thrift.server import THttpServer
from thrift.Thrift import TMessageType
from thrift.transport import TTransport


def getReqHandler(thttpserver: THttpServer.THttpServer):
    class RequestHander(BaseHTTPServer.BaseHTTPRequestHandler):
        def do_POST(self):
            # Don't care about the request path.
            thttpserver._replied = False
            iftrans = TTransport.TFileObjectTransport(self.rfile)
            itrans = TTransport.TBufferedTransport(iftrans, int(self.headers["Content-Length"]))
            otrans = TTransport.TMemoryBuffer()
            iprot = thttpserver.inputProtocolFactory.getProtocol(itrans)
            oprot = thttpserver.outputProtocolFactory.getProtocol(otrans)
            try:
                thttpserver.processor.on_message_begin(self.on_begin)
                thttpserver.processor.process(iprot, oprot)
            except THttpServer.ResponseException as exn:
                exn.handler(self)
            else:
                if not thttpserver._replied:
                    # If the request was ONEWAY we would have replied already
                    data = otrans.getvalue()
                    self.send_response(200)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", len(data))
                    self.send_header("Content-Type", "application/x-thrift")
                    self.end_headers()
                    self.wfile.write(data)

        def on_begin(self, name, type, seqid):
            """
            Inspect the message header.

            This allows us to post an immediate transport response
            if the request is a ONEWAY message type.
            """
            if type == TMessageType.ONEWAY:
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/x-thrift")
                self.end_headers()
                thttpserver._replied = True

    return RequestHander
