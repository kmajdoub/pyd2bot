#
# Autogenerated by Thrift Compiler (0.16.0)
#
# DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
#
#  options string: py
#

from thrift.Thrift import TType, TMessageType, TFrozenDict, TException, TApplicationException
from thrift.protocol.TProtocol import TProtocolException
from thrift.TRecursive import fix_spec

import sys
import logging
from .ttypes import *
from thrift.Thrift import TProcessor
from thrift.transport import TTransport
all_structs = []


class Iface(object):
    def fetchAccountCharacters(self, login, password, certId, certHash):
        """
        Parameters:
         - login
         - password
         - certId
         - certHash

        """
        pass

    def runSession(self, login, password, certId, certHash, sessionJson):
        """
        Parameters:
         - login
         - password
         - certId
         - certHash
         - sessionJson

        """
        pass


class Client(Iface):
    def __init__(self, iprot, oprot=None):
        self._iprot = self._oprot = iprot
        if oprot is not None:
            self._oprot = oprot
        self._seqid = 0

    def fetchAccountCharacters(self, login, password, certId, certHash):
        """
        Parameters:
         - login
         - password
         - certId
         - certHash

        """
        self.send_fetchAccountCharacters(login, password, certId, certHash)
        return self.recv_fetchAccountCharacters()

    def send_fetchAccountCharacters(self, login, password, certId, certHash):
        self._oprot.writeMessageBegin('fetchAccountCharacters', TMessageType.CALL, self._seqid)
        args = fetchAccountCharacters_args()
        args.login = login
        args.password = password
        args.certId = certId
        args.certHash = certHash
        args.write(self._oprot)
        self._oprot.writeMessageEnd()
        self._oprot.trans.flush()

    def recv_fetchAccountCharacters(self):
        iprot = self._iprot
        (fname, mtype, rseqid) = iprot.readMessageBegin()
        if mtype == TMessageType.EXCEPTION:
            x = TApplicationException()
            x.read(iprot)
            iprot.readMessageEnd()
            raise x
        result = fetchAccountCharacters_result()
        result.read(iprot)
        iprot.readMessageEnd()
        if result.success is not None:
            return result.success
        raise TApplicationException(TApplicationException.MISSING_RESULT, "fetchAccountCharacters failed: unknown result")

    def runSession(self, login, password, certId, certHash, sessionJson):
        """
        Parameters:
         - login
         - password
         - certId
         - certHash
         - sessionJson

        """
        self.send_runSession(login, password, certId, certHash, sessionJson)

    def send_runSession(self, login, password, certId, certHash, sessionJson):
        self._oprot.writeMessageBegin('runSession', TMessageType.ONEWAY, self._seqid)
        args = runSession_args()
        args.login = login
        args.password = password
        args.certId = certId
        args.certHash = certHash
        args.sessionJson = sessionJson
        args.write(self._oprot)
        self._oprot.writeMessageEnd()
        self._oprot.trans.flush()


class Processor(Iface, TProcessor):
    def __init__(self, handler):
        self._handler = handler
        self._processMap = {}
        self._processMap["fetchAccountCharacters"] = Processor.process_fetchAccountCharacters
        self._processMap["runSession"] = Processor.process_runSession
        self._on_message_begin = None

    def on_message_begin(self, func):
        self._on_message_begin = func

    def process(self, iprot, oprot):
        (name, type, seqid) = iprot.readMessageBegin()
        if self._on_message_begin:
            self._on_message_begin(name, type, seqid)
        if name not in self._processMap:
            iprot.skip(TType.STRUCT)
            iprot.readMessageEnd()
            x = TApplicationException(TApplicationException.UNKNOWN_METHOD, 'Unknown function %s' % (name))
            oprot.writeMessageBegin(name, TMessageType.EXCEPTION, seqid)
            x.write(oprot)
            oprot.writeMessageEnd()
            oprot.trans.flush()
            return
        else:
            self._processMap[name](self, seqid, iprot, oprot)
        return True

    def process_fetchAccountCharacters(self, seqid, iprot, oprot):
        args = fetchAccountCharacters_args()
        args.read(iprot)
        iprot.readMessageEnd()
        result = fetchAccountCharacters_result()
        try:
            result.success = self._handler.fetchAccountCharacters(args.login, args.password, args.certId, args.certHash)
            msg_type = TMessageType.REPLY
        except TTransport.TTransportException:
            raise
        except TApplicationException as ex:
            logging.exception('TApplication exception in handler')
            msg_type = TMessageType.EXCEPTION
            result = ex
        except Exception:
            logging.exception('Unexpected exception in handler')
            msg_type = TMessageType.EXCEPTION
            result = TApplicationException(TApplicationException.INTERNAL_ERROR, 'Internal error')
        oprot.writeMessageBegin("fetchAccountCharacters", msg_type, seqid)
        result.write(oprot)
        oprot.writeMessageEnd()
        oprot.trans.flush()

    def process_runSession(self, seqid, iprot, oprot):
        args = runSession_args()
        args.read(iprot)
        iprot.readMessageEnd()
        try:
            self._handler.runSession(args.login, args.password, args.certId, args.certHash, args.sessionJson)
        except TTransport.TTransportException:
            raise
        except Exception:
            logging.exception('Exception in oneway handler')

# HELPER FUNCTIONS AND STRUCTURES


class fetchAccountCharacters_args(object):
    """
    Attributes:
     - login
     - password
     - certId
     - certHash

    """


    def __init__(self, login=None, password=None, certId=None, certHash=None,):
        self.login = login
        self.password = password
        self.certId = certId
        self.certHash = certHash

    def read(self, iprot):
        if iprot._fast_decode is not None and isinstance(iprot.trans, TTransport.CReadableTransport) and self.thrift_spec is not None:
            iprot._fast_decode(self, iprot, [self.__class__, self.thrift_spec])
            return
        iprot.readStructBegin()
        while True:
            (fname, ftype, fid) = iprot.readFieldBegin()
            if ftype == TType.STOP:
                break
            if fid == 1:
                if ftype == TType.STRING:
                    self.login = iprot.readString().decode('utf-8', errors='replace') if sys.version_info[0] == 2 else iprot.readString()
                else:
                    iprot.skip(ftype)
            elif fid == 2:
                if ftype == TType.STRING:
                    self.password = iprot.readString().decode('utf-8', errors='replace') if sys.version_info[0] == 2 else iprot.readString()
                else:
                    iprot.skip(ftype)
            elif fid == 3:
                if ftype == TType.I32:
                    self.certId = iprot.readI32()
                else:
                    iprot.skip(ftype)
            elif fid == 4:
                if ftype == TType.STRING:
                    self.certHash = iprot.readString().decode('utf-8', errors='replace') if sys.version_info[0] == 2 else iprot.readString()
                else:
                    iprot.skip(ftype)
            else:
                iprot.skip(ftype)
            iprot.readFieldEnd()
        iprot.readStructEnd()

    def write(self, oprot):
        if oprot._fast_encode is not None and self.thrift_spec is not None:
            oprot.trans.write(oprot._fast_encode(self, [self.__class__, self.thrift_spec]))
            return
        oprot.writeStructBegin('fetchAccountCharacters_args')
        if self.login is not None:
            oprot.writeFieldBegin('login', TType.STRING, 1)
            oprot.writeString(self.login.encode('utf-8') if sys.version_info[0] == 2 else self.login)
            oprot.writeFieldEnd()
        if self.password is not None:
            oprot.writeFieldBegin('password', TType.STRING, 2)
            oprot.writeString(self.password.encode('utf-8') if sys.version_info[0] == 2 else self.password)
            oprot.writeFieldEnd()
        if self.certId is not None:
            oprot.writeFieldBegin('certId', TType.I32, 3)
            oprot.writeI32(self.certId)
            oprot.writeFieldEnd()
        if self.certHash is not None:
            oprot.writeFieldBegin('certHash', TType.STRING, 4)
            oprot.writeString(self.certHash.encode('utf-8') if sys.version_info[0] == 2 else self.certHash)
            oprot.writeFieldEnd()
        oprot.writeFieldStop()
        oprot.writeStructEnd()

    def validate(self):
        return

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not (self == other)
all_structs.append(fetchAccountCharacters_args)
fetchAccountCharacters_args.thrift_spec = (
    None,  # 0
    (1, TType.STRING, 'login', 'UTF8', None, ),  # 1
    (2, TType.STRING, 'password', 'UTF8', None, ),  # 2
    (3, TType.I32, 'certId', None, None, ),  # 3
    (4, TType.STRING, 'certHash', 'UTF8', None, ),  # 4
)


class fetchAccountCharacters_result(object):
    """
    Attributes:
     - success

    """


    def __init__(self, success=None,):
        self.success = success

    def read(self, iprot):
        if iprot._fast_decode is not None and isinstance(iprot.trans, TTransport.CReadableTransport) and self.thrift_spec is not None:
            iprot._fast_decode(self, iprot, [self.__class__, self.thrift_spec])
            return
        iprot.readStructBegin()
        while True:
            (fname, ftype, fid) = iprot.readFieldBegin()
            if ftype == TType.STOP:
                break
            if fid == 0:
                if ftype == TType.LIST:
                    self.success = []
                    (_etype10, _size7) = iprot.readListBegin()
                    for _i11 in range(_size7):
                        _elem12 = Character()
                        _elem12.read(iprot)
                        self.success.append(_elem12)
                    iprot.readListEnd()
                else:
                    iprot.skip(ftype)
            else:
                iprot.skip(ftype)
            iprot.readFieldEnd()
        iprot.readStructEnd()

    def write(self, oprot):
        if oprot._fast_encode is not None and self.thrift_spec is not None:
            oprot.trans.write(oprot._fast_encode(self, [self.__class__, self.thrift_spec]))
            return
        oprot.writeStructBegin('fetchAccountCharacters_result')
        if self.success is not None:
            oprot.writeFieldBegin('success', TType.LIST, 0)
            oprot.writeListBegin(TType.STRUCT, len(self.success))
            for iter13 in self.success:
                iter13.write(oprot)
            oprot.writeListEnd()
            oprot.writeFieldEnd()
        oprot.writeFieldStop()
        oprot.writeStructEnd()

    def validate(self):
        return

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not (self == other)
all_structs.append(fetchAccountCharacters_result)
fetchAccountCharacters_result.thrift_spec = (
    (0, TType.LIST, 'success', (TType.STRUCT, [Character, None], False), None, ),  # 0
)


class runSession_args(object):
    """
    Attributes:
     - login
     - password
     - certId
     - certHash
     - sessionJson

    """


    def __init__(self, login=None, password=None, certId=None, certHash=None, sessionJson=None,):
        self.login = login
        self.password = password
        self.certId = certId
        self.certHash = certHash
        self.sessionJson = sessionJson

    def read(self, iprot):
        if iprot._fast_decode is not None and isinstance(iprot.trans, TTransport.CReadableTransport) and self.thrift_spec is not None:
            iprot._fast_decode(self, iprot, [self.__class__, self.thrift_spec])
            return
        iprot.readStructBegin()
        while True:
            (fname, ftype, fid) = iprot.readFieldBegin()
            if ftype == TType.STOP:
                break
            if fid == 1:
                if ftype == TType.STRING:
                    self.login = iprot.readString().decode('utf-8', errors='replace') if sys.version_info[0] == 2 else iprot.readString()
                else:
                    iprot.skip(ftype)
            elif fid == 2:
                if ftype == TType.STRING:
                    self.password = iprot.readString().decode('utf-8', errors='replace') if sys.version_info[0] == 2 else iprot.readString()
                else:
                    iprot.skip(ftype)
            elif fid == 3:
                if ftype == TType.I32:
                    self.certId = iprot.readI32()
                else:
                    iprot.skip(ftype)
            elif fid == 4:
                if ftype == TType.STRING:
                    self.certHash = iprot.readString().decode('utf-8', errors='replace') if sys.version_info[0] == 2 else iprot.readString()
                else:
                    iprot.skip(ftype)
            elif fid == 5:
                if ftype == TType.STRING:
                    self.sessionJson = iprot.readString().decode('utf-8', errors='replace') if sys.version_info[0] == 2 else iprot.readString()
                else:
                    iprot.skip(ftype)
            else:
                iprot.skip(ftype)
            iprot.readFieldEnd()
        iprot.readStructEnd()

    def write(self, oprot):
        if oprot._fast_encode is not None and self.thrift_spec is not None:
            oprot.trans.write(oprot._fast_encode(self, [self.__class__, self.thrift_spec]))
            return
        oprot.writeStructBegin('runSession_args')
        if self.login is not None:
            oprot.writeFieldBegin('login', TType.STRING, 1)
            oprot.writeString(self.login.encode('utf-8') if sys.version_info[0] == 2 else self.login)
            oprot.writeFieldEnd()
        if self.password is not None:
            oprot.writeFieldBegin('password', TType.STRING, 2)
            oprot.writeString(self.password.encode('utf-8') if sys.version_info[0] == 2 else self.password)
            oprot.writeFieldEnd()
        if self.certId is not None:
            oprot.writeFieldBegin('certId', TType.I32, 3)
            oprot.writeI32(self.certId)
            oprot.writeFieldEnd()
        if self.certHash is not None:
            oprot.writeFieldBegin('certHash', TType.STRING, 4)
            oprot.writeString(self.certHash.encode('utf-8') if sys.version_info[0] == 2 else self.certHash)
            oprot.writeFieldEnd()
        if self.sessionJson is not None:
            oprot.writeFieldBegin('sessionJson', TType.STRING, 5)
            oprot.writeString(self.sessionJson.encode('utf-8') if sys.version_info[0] == 2 else self.sessionJson)
            oprot.writeFieldEnd()
        oprot.writeFieldStop()
        oprot.writeStructEnd()

    def validate(self):
        return

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not (self == other)
all_structs.append(runSession_args)
runSession_args.thrift_spec = (
    None,  # 0
    (1, TType.STRING, 'login', 'UTF8', None, ),  # 1
    (2, TType.STRING, 'password', 'UTF8', None, ),  # 2
    (3, TType.I32, 'certId', None, None, ),  # 3
    (4, TType.STRING, 'certHash', 'UTF8', None, ),  # 4
    (5, TType.STRING, 'sessionJson', 'UTF8', None, ),  # 5
)
fix_spec(all_structs)
del all_structs
