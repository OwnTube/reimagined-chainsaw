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
    std::cout<<"Property reader: literal/cached scopes, raw IDs, control flags, fixed Huffman word, truncation and trailing data passed\n";
}
