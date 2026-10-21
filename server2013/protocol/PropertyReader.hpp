// Original bounded exact-build property reader. Public RakNet Huffman format;
// frequency data/notices are in EnglishFrequencies.hpp and raknet_reference/.
#pragma once
#include "EnglishFrequencies.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>
namespace rcc2013 {
class BitReader {
    const std::vector<uint8_t>& bytes_;size_t limit_,offset_=0;
public:
    BitReader(const std::vector<uint8_t>& bytes,size_t bits):bytes_(bytes),limit_(bits) {
        if(!bits || bits>bytes.size()*8 || (bits+7)/8!=bytes.size() || bytes.size()>128*1024)
            throw std::runtime_error("property reader byte/bit bound");
    }
    uint32_t uint32(unsigned width) {
        if(width>32 || width>remaining())throw std::runtime_error("property reader truncation");
        uint32_t n=0;for(unsigned i=0;i<width;++i,++offset_)n=(n<<1)|((bytes_[offset_/8]>>(7-offset_%8))&1);
        return n;
    }
    uint32_t rawLittle(unsigned width) {
        if(width>32)throw std::runtime_error("raw integer bound");
        uint32_t n=0;for(unsigned shift=0;shift<width;shift+=8)n|=uint32(std::min(8u,width-shift))<<shift;
        return n;
    }
    void skip(unsigned width){while(width){const unsigned n=std::min(32u,width);uint32(n);width-=n;}}
    size_t remaining()const{return limit_-offset_;}
    uint32_t compressed() {
        std::array<uint8_t,4> raw{};
        for(int i=3;i>0;--i)if(!uint32(1)) {
            for(int j=0;j<=i;++j)raw[j]=static_cast<uint8_t>(uint32(8));
            return (uint32_t(raw[0])<<24)|(uint32_t(raw[1])<<16)|(uint32_t(raw[2])<<8)|raw[3];
        }
        raw[0]=static_cast<uint8_t>(uint32(uint32(1)?4:8));return uint32_t(raw[0])<<24;
    }
};
struct StringProperty {std::string scope,value;uint32_t index=0;bool control=false;};
class PropertyReader {
    struct Node{uint32_t weight;int symbol,left,right;};
    std::vector<Node> tree_;
    std::array<std::string,128> scopes_{},values_{};
    uint32_t valueDescriptor_=735;
    bool controlBit_;
    std::string text(BitReader& in,unsigned maximum=128)const {
        const auto length=in.uint32(32),bits=in.compressed();
        if(length>maximum || bits>8192 || bits>in.remaining())throw std::runtime_error("cached text bound");
        std::string value;int node=static_cast<int>(tree_.size()-1);
        for(uint32_t i=0;i<bits;++i){node=in.uint32(1)?tree_[node].right:tree_[node].left;
            if(tree_[node].symbol>=0){const auto c=tree_[node].symbol;if(c<32||c>126||value.size()>=maximum)throw std::runtime_error("cached text alphabet/size");value+=static_cast<char>(c);node=static_cast<int>(tree_.size()-1);}}
        if(value.size()!=length)throw std::runtime_error("cached text decoded length");
        return value;
    }
    std::string cached(BitReader& in,std::array<std::string,128>& cache,const char* kind)const {
        const auto code=in.uint32(8),slot=code&127;
        if(!code)return {};
        if(!slot)throw std::runtime_error("invalid cache slot");
        if(code&128)cache[slot]=text(in);
        else if(cache[slot].empty())throw std::runtime_error(std::string("unknown ")+kind+" cache slot "+std::to_string(slot));
        return cache[slot];
    }
public:
    explicit PropertyReader(bool controlBit=true):controlBit_(controlBit){
        std::vector<int> ordered;
        auto insert=[&](int id){auto at=std::lower_bound(ordered.begin(),ordered.end(),tree_[id].weight,
            [&](int other,uint32_t w){return tree_[other].weight<w;});ordered.insert(at,id);};
        for(int i=0;i<256;++i){tree_.push_back({std::max(uint32_t(1),englishFrequencies[i]),i,-1,-1});insert(i);}
        while(ordered.size()>1){int a=ordered[0],b=ordered[1];ordered.erase(ordered.begin(),ordered.begin()+2);
            tree_.push_back({tree_[a].weight+tree_[b].weight,-1,a,b});insert(static_cast<int>(tree_.size()-1));}
    }
    struct DescriptorPrefix {std::vector<uint32_t> counts;uint32_t valueId=0;size_t remainingBits=0;};
    DescriptorPrefix descriptors(const std::vector<uint8_t>& body,size_t bits){
        BitReader in(body,bits);if(in.uint32(8)!=0x82)throw std::runtime_error("not descriptors");
        DescriptorPrefix result;bool found=false;
        for(unsigned table=0;table<3;++table){
            const auto count=in.uint32(32);if(!count||count>4096)throw std::runtime_error("descriptor count bound");
            result.counts.push_back(count);std::vector<bool> seen(count,false);
            for(uint32_t entry=0;entry<count;++entry){
                const auto id=in.uint32(32);if(id>=count||seen[id])throw std::runtime_error("descriptor ID identity");seen[id]=true;
                auto name=text(in,255);
                if(table==1 && name=="StringValue:Value"){
                    if(found)throw std::runtime_error("ambiguous Value descriptor");
                    found=true;result.valueId=id;
                }
            }
        }
        if(result.counts[1]<=512 || result.counts[1]>1024)throw std::runtime_error("unsupported property ID width");
        if(!found || result.valueId>=1024)throw std::runtime_error("missing bounded Value descriptor");
        result.remainingBits=in.remaining();valueDescriptor_=result.valueId;return result;
    }
    // Only supported ID3 StringValue.Value entries are returned. Other packets
    // are rejected whole; no guessed skipping of unknown application fields.
    std::vector<StringProperty> read(const std::vector<uint8_t>& body,size_t bits){
        if(body.size()>4096)throw std::runtime_error("property packet size bound");
        BitReader in(body,bits);if(in.uint32(8)!=0x83)throw std::runtime_error("not replication");
        auto scopes=scopes_,values=values_;std::vector<StringProperty> result;
        for(unsigned items=0;items<32;++items){
            auto id=in.uint32(2);if(!id)id=in.uint32(4);
            if(!id){if(in.remaining()>7 || (in.remaining() && in.uint32(static_cast<unsigned>(in.remaining()))))throw std::runtime_error("replication trailing bits");scopes_=std::move(scopes);values_=std::move(values);return result;}
            if(id==5||id==6){in.skip(97);continue;} // measured bit + uint64 + uint32 ping payload
            if(id!=3)throw std::runtime_error("unsupported replication item "+std::to_string(id));
            StringProperty property;property.scope=cached(in,scopes,"scope");
            if(property.scope.empty())throw std::runtime_error("null property GUID");
            property.index=in.rawLittle(32);auto descriptor=in.rawLittle(10);
            if(descriptor!=valueDescriptor_)throw std::runtime_error("unsupported property descriptor "+std::to_string(descriptor));
            property.control=controlBit_ && in.uint32(1)!=0;property.value=cached(in,values,"value");result.push_back(std::move(property));
        }
        throw std::runtime_error("replication item budget");
    }
};
}
