package com.ankamagames.dofus.network.messages.game.social
{
    import com.ankamagames.jerakine.network.CustomDataWrapper;
    import com.ankamagames.jerakine.network.ICustomDataInput;
    import com.ankamagames.jerakine.network.ICustomDataOutput;
    import com.ankamagames.jerakine.network.INetworkMessage;
    import com.ankamagames.jerakine.network.NetworkMessage;
    import com.ankamagames.jerakine.network.utils.FuncTree;
    import flash.utils.ByteArray;
    
    public class SocialNoticeSetRequestMessage extends NetworkMessage implements INetworkMessage
    {
        
        public static const protocolId:uint = 3375;
         
        
        public function SocialNoticeSetRequestMessage()
        {
            super();
        }
        
        override public function get isInitialized() : Boolean
        {
            return true;
        }
        
        override public function getMessageId() : uint
        {
            return 3375;
        }
        
        public function initSocialNoticeSetRequestMessage() : SocialNoticeSetRequestMessage
        {
            return this;
        }
        
        override public function reset() : void
        {
        }
        
        override public function pack(output:ICustomDataOutput) : void
        {
            var data:ByteArray = new ByteArray();
            this.serialize(new CustomDataWrapper(data));
            writePacket(output,this.getMessageId(),data);
        }
        
        override public function unpack(input:ICustomDataInput, length:uint) : void
        {
            this.deserialize(input);
        }
        
        override public function unpackAsync(input:ICustomDataInput, length:uint) : FuncTree
        {
            var tree:FuncTree = new FuncTree();
            tree.setRoot(input);
            this.deserializeAsync(tree);
            return tree;
        }
        
        public function serialize(output:ICustomDataOutput) : void
        {
        }
        
        public function serializeAs_SocialNoticeSetRequestMessage(output:ICustomDataOutput) : void
        {
        }
        
        public function deserialize(input:ICustomDataInput) : void
        {
        }
        
        public function deserializeAs_SocialNoticeSetRequestMessage(input:ICustomDataInput) : void
        {
        }
        
        public function deserializeAsync(tree:FuncTree) : void
        {
        }
        
        public function deserializeAsyncAs_SocialNoticeSetRequestMessage(tree:FuncTree) : void
        {
        }
    }
}
