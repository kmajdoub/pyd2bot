//
// Autogenerated by Thrift Compiler (0.16.0)
//
// DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
//
"use strict";

var thrift = require('thrift');
var Thrift = thrift.Thrift;
var Q = thrift.Q;
var Int64 = require('node-int64');


var ttypes = module.exports = {};
var Spell = module.exports.Spell = function(args) {
  this.id = null;
  this.name = null;
  this.description = null;
  if (args) {
    if (args.id !== undefined && args.id !== null) {
      this.id = args.id;
    }
    if (args.name !== undefined && args.name !== null) {
      this.name = args.name;
    }
    if (args.description !== undefined && args.description !== null) {
      this.description = args.description;
    }
  }
};
Spell.prototype = {};
Spell.prototype.read = function(input) {
  input.readStructBegin();
  while (true) {
    var ret = input.readFieldBegin();
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid) {
      case 1:
      if (ftype == Thrift.Type.I32) {
        this.id = input.readI32();
      } else {
        input.skip(ftype);
      }
      break;
      case 2:
      if (ftype == Thrift.Type.STRING) {
        this.name = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      case 3:
      if (ftype == Thrift.Type.STRING) {
        this.description = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

Spell.prototype.write = function(output) {
  output.writeStructBegin('Spell');
  if (this.id !== null && this.id !== undefined) {
    output.writeFieldBegin('id', Thrift.Type.I32, 1);
    output.writeI32(this.id);
    output.writeFieldEnd();
  }
  if (this.name !== null && this.name !== undefined) {
    output.writeFieldBegin('name', Thrift.Type.STRING, 2);
    output.writeString(this.name);
    output.writeFieldEnd();
  }
  if (this.description !== null && this.description !== undefined) {
    output.writeFieldBegin('description', Thrift.Type.STRING, 3);
    output.writeString(this.description);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var Character = module.exports.Character = function(args) {
  this.name = null;
  this.id = null;
  this.level = null;
  this.breedId = null;
  this.breedName = null;
  this.serverId = null;
  this.serverName = null;
  this.spells = null;
  if (args) {
    if (args.name !== undefined && args.name !== null) {
      this.name = args.name;
    }
    if (args.id !== undefined && args.id !== null) {
      this.id = args.id;
    }
    if (args.level !== undefined && args.level !== null) {
      this.level = args.level;
    }
    if (args.breedId !== undefined && args.breedId !== null) {
      this.breedId = args.breedId;
    }
    if (args.breedName !== undefined && args.breedName !== null) {
      this.breedName = args.breedName;
    }
    if (args.serverId !== undefined && args.serverId !== null) {
      this.serverId = args.serverId;
    }
    if (args.serverName !== undefined && args.serverName !== null) {
      this.serverName = args.serverName;
    }
    if (args.spells !== undefined && args.spells !== null) {
      this.spells = Thrift.copyList(args.spells, [ttypes.Spell]);
    }
  }
};
Character.prototype = {};
Character.prototype.read = function(input) {
  input.readStructBegin();
  while (true) {
    var ret = input.readFieldBegin();
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid) {
      case 1:
      if (ftype == Thrift.Type.STRING) {
        this.name = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      case 2:
      if (ftype == Thrift.Type.DOUBLE) {
        this.id = input.readDouble();
      } else {
        input.skip(ftype);
      }
      break;
      case 3:
      if (ftype == Thrift.Type.I32) {
        this.level = input.readI32();
      } else {
        input.skip(ftype);
      }
      break;
      case 4:
      if (ftype == Thrift.Type.I32) {
        this.breedId = input.readI32();
      } else {
        input.skip(ftype);
      }
      break;
      case 5:
      if (ftype == Thrift.Type.STRING) {
        this.breedName = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      case 6:
      if (ftype == Thrift.Type.I32) {
        this.serverId = input.readI32();
      } else {
        input.skip(ftype);
      }
      break;
      case 7:
      if (ftype == Thrift.Type.STRING) {
        this.serverName = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      case 8:
      if (ftype == Thrift.Type.LIST) {
        this.spells = [];
        var _rtmp31 = input.readListBegin();
        var _size0 = _rtmp31.size || 0;
        for (var _i2 = 0; _i2 < _size0; ++_i2) {
          var elem3 = null;
          elem3 = new ttypes.Spell();
          elem3.read(input);
          this.spells.push(elem3);
        }
        input.readListEnd();
      } else {
        input.skip(ftype);
      }
      break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

Character.prototype.write = function(output) {
  output.writeStructBegin('Character');
  if (this.name !== null && this.name !== undefined) {
    output.writeFieldBegin('name', Thrift.Type.STRING, 1);
    output.writeString(this.name);
    output.writeFieldEnd();
  }
  if (this.id !== null && this.id !== undefined) {
    output.writeFieldBegin('id', Thrift.Type.DOUBLE, 2);
    output.writeDouble(this.id);
    output.writeFieldEnd();
  }
  if (this.level !== null && this.level !== undefined) {
    output.writeFieldBegin('level', Thrift.Type.I32, 3);
    output.writeI32(this.level);
    output.writeFieldEnd();
  }
  if (this.breedId !== null && this.breedId !== undefined) {
    output.writeFieldBegin('breedId', Thrift.Type.I32, 4);
    output.writeI32(this.breedId);
    output.writeFieldEnd();
  }
  if (this.breedName !== null && this.breedName !== undefined) {
    output.writeFieldBegin('breedName', Thrift.Type.STRING, 5);
    output.writeString(this.breedName);
    output.writeFieldEnd();
  }
  if (this.serverId !== null && this.serverId !== undefined) {
    output.writeFieldBegin('serverId', Thrift.Type.I32, 6);
    output.writeI32(this.serverId);
    output.writeFieldEnd();
  }
  if (this.serverName !== null && this.serverName !== undefined) {
    output.writeFieldBegin('serverName', Thrift.Type.STRING, 7);
    output.writeString(this.serverName);
    output.writeFieldEnd();
  }
  if (this.spells !== null && this.spells !== undefined) {
    output.writeFieldBegin('spells', Thrift.Type.LIST, 8);
    output.writeListBegin(Thrift.Type.STRUCT, this.spells.length);
    for (var iter4 in this.spells) {
      if (this.spells.hasOwnProperty(iter4)) {
        iter4 = this.spells[iter4];
        iter4.write(output);
      }
    }
    output.writeListEnd();
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

