#include "DescriptorWriter.hpp"
#include "PropertyReader.hpp"
#include <cassert>
#include <iostream>
int main(){
    rcc2013::DescriptorWriter writer;rcc2013::PropertyReader reader;
    const std::string scope="RBX0123456789abcdef0123456789abcdef",nonce="RCC2013_0123456789abcdef0123456789abcdef_ack";
    auto first=writer.valueProperty(0x23456789,nonce,1,scope,true);
    auto decoded=reader.read(first.bytes(),first.sizeBits());
    assert(decoded.size()==1 && decoded[0].index==0x23456789 && decoded[0].scope==scope && decoded[0].value==nonce && decoded[0].control);
    auto next=writer.valueProperty(0x23456789,"SecondValue",2);
    decoded=reader.read(next.bytes(),next.sizeBits());assert(decoded[0].value=="SecondValue" && decoded[0].scope==scope && !decoded[0].control);
    for(size_t i=1;i<first.bytes().size();++i){rcc2013::PropertyReader fresh;bool failed=false;
        try{fresh.read(std::vector<uint8_t>(first.bytes().begin(),first.bytes().begin()+i),i*8);}catch(const std::runtime_error&){failed=true;}assert(failed);}
    rcc2013::PropertyReader empty;bool unknown=false;try{empty.read(next.bytes(),next.sizeBits());}catch(const std::runtime_error&){unknown=true;}assert(unknown);
    auto corrupt=first.bytes();corrupt.push_back(255);bool rejected=false;
    try{reader.read(corrupt,first.sizeBits()+8);}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    // Public fixed Huffman word "Name": decoder fixture does not use our encoder.
    rcc2013::BitWriter fixture;fixture.uint32(0x83,8);fixture.uint32(3,2);
    fixture.uint32(0x81,8);fixture.uint32(4,32);fixture.bit(false);fixture.uint32(24,32);
    fixture.uint32(0x31,8);fixture.uint32(0x36,8);fixture.uint32(0x81,8);
    for(unsigned i=0;i<4;++i)fixture.uint32((0x23456789>>(8*i))&255,8);
    fixture.uint32(0xdf,8);fixture.uint32(2,2);fixture.bit(false);
    fixture.uint32(0x81,8);fixture.uint32(4,32);fixture.bit(false);fixture.uint32(24,32);
    fixture.uint32(0x31,8);fixture.uint32(0x36,8);fixture.uint32(0x81,8);fixture.uint32(0,6);
    decoded=empty.read(fixture.bytes(),fixture.sizeBits());assert(decoded[0].scope=="Name" && decoded[0].value=="Name");
    // The peer's descriptor IDs are independent from our outgoing IDs.
    std::vector<rcc2013::Dictionary> tables(4);
    tables[0].push_back({0,"Part"});tables[2].push_back({0,"OwnedEvent"});tables[3].push_back({0,"OwnedType"});
    for(uint32_t i=0;i<513;++i)tables[1].push_back({i,i==19?"StringValue:Value":"OwnedProperty"+std::to_string(i)});
    auto schema=writer.dictionaries(tables);auto prefix=reader.descriptors(schema.bytes(),schema.sizeBits());
    assert(prefix.valueId==19 && prefix.counts[1]==513 && prefix.remainingBits>0);
    rcc2013::BitWriter reply;reply.uint32(0x83,8);reply.uint32(3,2);reply.uint32(1,8);
    for(unsigned i=0;i<4;++i)reply.uint32((0x23456789>>(8*i))&255,8);
    reply.uint32(19,8);reply.uint32(0,2);reply.bit(true);reply.uint32(1,8);reply.uint32(0,6);
    decoded=reader.read(reply.bytes(),reply.sizeBits());assert(decoded[0].value==nonce && decoded[0].scope==scope);
    // Directional fixture: client updates omit the server's control bit. An
    // erroneous extra read shifts literal 0x81 to an unresolved cached slot2.
    rcc2013::BitWriter client;client.uint32(0x83,8);client.uint32(3,2);
    auto fixedText=[&](){client.uint32(4,32);client.bit(false);client.uint32(24,32);client.uint32(0x31,8);client.uint32(0x36,8);client.uint32(0x81,8);};
    client.uint32(0x81,8);fixedText();
    for(unsigned i=0;i<4;++i)client.uint32((0x23456789>>(8*i))&255,8);
    client.uint32(0xdf,8);client.uint32(2,2);client.uint32(0x81,8);fixedText();client.uint32(0,6);
    rcc2013::PropertyReader upstream(false);decoded=upstream.read(client.bytes(),client.sizeBits());
    assert(decoded[0].value=="Name" && decoded[0].scope=="Name");
    rcc2013::PropertyReader downstream;rejected=false;
    try{downstream.read(client.bytes(),client.sizeBits());}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    std::cout<<"Property reader: literal/cached scopes, raw IDs, control flags, fixed Huffman word, truncation and trailing data passed\n";
}
