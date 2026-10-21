// Original bounded C++ descriptor encoder. No Roblox engine code or replay.
// Huffman interoperability follows the public BSD RakNet reference; its English
// table and notices are identified by EnglishFrequencies.hpp.
#pragma once
#include "EnglishFrequencies.hpp"
#include <algorithm>
#include <cstdint>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace rcc2013 {
class BitWriter {
    std::vector<uint8_t> data_;
    size_t bits_=0;
public:
    void bit(bool value) {
        if(bits_>=128*1024*8) throw std::runtime_error("bit budget exceeded");
        if(bits_%8==0) data_.push_back(0);
        if(value) data_.back()|=uint8_t(0x80>>(bits_%8));
        ++bits_;
    }
    void uint32(uint32_t value,unsigned width) {
        if(width>32 || (width<32 && (value>>width)!=0))
            throw std::runtime_error("integer width exceeded");
        for(unsigned i=width;i>0;--i) bit(((value>>(i-1))&1)!=0);
    }
    void compressedUint32(uint32_t value) {
        // RakNet tests the high memory byte first. A network-endian integer's
        // bytes are already reversed relative to little-endian host storage.
        uint8_t raw[4]={uint8_t(value>>24),uint8_t(value>>16),uint8_t(value>>8),uint8_t(value)};
        for(int index=3;index>0;--index) {
            if(raw[index]==0) {bit(true);continue;}
            bit(false);
            for(int i=0;i<=index;++i) uint32(raw[i],8);
            return;
        }
        const bool nibble=raw[0]<16;
        bit(nibble);uint32(raw[0],nibble?4:8);
    }
    void align() {while(bits_%8)bit(false);}
    size_t sizeBits() const {return bits_;}
    const std::vector<uint8_t>& bytes() const {return data_;}
};

struct Descriptor {uint32_t id;std::string name;};
using Dictionary=std::vector<Descriptor>;
class DescriptorWriter {
    struct Node {uint32_t weight;int symbol,left,right;};
    std::vector<Node> nodes_;
    std::vector<std::vector<bool>> codes_{256};
    void paths(int index,std::vector<bool>& path) {
        const auto& n=nodes_[index];
        if(n.symbol>=0) {codes_[n.symbol]=path;return;}
        path.push_back(false);paths(n.left,path);
        path.back()=true;paths(n.right,path);path.pop_back();
    }
    void string(BitWriter& output,const std::string& text) const {
        std::vector<bool> encoded;
        for(unsigned char c:text) encoded.insert(encoded.end(),codes_[c].begin(),codes_[c].end());
        if(encoded.size()%8) {
            const auto padding=8-encoded.size()%8;
            for(const auto& code:codes_) if(code.size()>padding) {
                encoded.insert(encoded.end(),code.begin(),code.begin()+padding);break;
            }
        }
        output.compressedUint32(static_cast<uint32_t>(encoded.size()));
        for(bool b:encoded) output.bit(b);
    }
public:
    DescriptorWriter() {
        std::vector<int> ordered;
        auto insert=[&](int index) {
            auto at=std::lower_bound(ordered.begin(),ordered.end(),nodes_[index].weight,
                [&](int other,uint32_t weight){return nodes_[other].weight<weight;});
            ordered.insert(at,index);
        };
        for(int c=0;c<256;++c) {
            nodes_.push_back({std::max(uint32_t(1),englishFrequencies[c]),c,-1,-1});
            insert(c);
        }
        while(ordered.size()>1) {
            const int left=ordered[0],right=ordered[1];ordered.erase(ordered.begin(),ordered.begin()+2);
            nodes_.push_back({nodes_[left].weight+nodes_[right].weight,-1,left,right});
            insert(static_cast<int>(nodes_.size()-1));
        }
        std::vector<bool> path;paths(ordered[0],path);
    }
    BitWriter dictionaries(const std::vector<Dictionary>& tables) const {
        if(tables.size()!=4) throw std::runtime_error("expected four dictionaries");
        BitWriter output;output.uint32(0x82,8);
        for(const auto& table:tables) {
            if(table.size()>4096) throw std::runtime_error("descriptor count exceeded");
            output.uint32(static_cast<uint32_t>(table.size()),32);
            std::set<uint32_t> seen;
            for(const auto& entry:table) {
                if(entry.id>=table.size() || !seen.insert(entry.id).second)
                    throw std::runtime_error("descriptor IDs must form a dense unique set");
                if(entry.name.empty() || entry.name.size()>255)
                    throw std::runtime_error("descriptor name length exceeded");
                for(unsigned char c:entry.name) if(c<32 || c>=127)
                    throw std::runtime_error("non-ASCII descriptor name");
                output.uint32(entry.id,32);output.uint32(static_cast<uint32_t>(entry.name.size()),32);
                string(output,entry.name);
            }
        }
        return output;
    }
    BitWriter schema(const std::vector<Dictionary>& tables,
                     const std::vector<std::pair<std::string,std::string>>& configuration) const {
        if(configuration.size()>512)throw std::runtime_error("configuration count bound");
        auto output=dictionaries(tables);
        output.uint32(static_cast<uint32_t>(configuration.size()),16);
        for(const auto& pair:configuration)for(const auto* field:{&pair.first,&pair.second}) {
            if(field->size()>2048)throw std::runtime_error("configuration string bound");
            output.uint32(static_cast<uint32_t>(field->size()),16);output.align();
            for(unsigned char c:*field)output.uint32(c,8);
        }
        return output;
    }
    // Exact-build property hypothesis: cached scope 1 established by globals,
    // ID3 compact item, raw x86 10-bit property ID, one false control bit,
    // a fresh per-property string-cache literal, then compact terminator 0.
    BitWriter serviceName(uint32_t index,const std::string& value) const {
        if(index<0x20000000 || index>0x3fffffff || value.empty() || value.size()>128)
            throw std::runtime_error("owned service name bounds");
        for(unsigned char c:value)if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'))
            throw std::runtime_error("owned service name alphabet");
        BitWriter out;out.uint32(0x83,8);out.uint32(3,2);out.uint32(1,8);
        for(unsigned byte=0;byte<4;++byte)out.uint32((index>>(byte*8))&255,8);
        // Instance:Name = 404 (0x0194). ReadBits(...,10,true) fills x86
        // memory byte 0 first, then a right-aligned two-bit high byte.
        out.uint32(0x94,8);out.uint32(1,2);out.bit(false);
        out.uint32(0x81,8);out.uint32(static_cast<uint32_t>(value.size()),32);string(out,value);
        out.uint32(0,6);return out;
    }
    // Measured StringValue reflection order: string Name, string Value, then
    // bool Archivable, bool RobloxLocked. Parent is a separate trailing GUID.
    // Name cache slot 1 was used by serviceName(); this new name uses slot 2.
    BitWriter stringValue(uint32_t index,uint32_t parent,const std::string& nonce) const {
        if(index<0x20000000 || index>0x3fffffff || parent<0x20000000 || parent>0x3fffffff
           || nonce.size()!=40 || nonce.substr(0,8)!="RCC2013_")
            throw std::runtime_error("owned instance bounds");
        for(char c:nonce.substr(8))if(!((c>='a'&&c<='f')||(c>='0'&&c<='9')))
            throw std::runtime_error("owned instance nonce alphabet");
        BitWriter out;out.uint32(0x83,8);out.uint32(2,2);out.uint32(1,8);
        for(unsigned byte=0;byte<4;++byte)out.uint32((index>>(byte*8))&255,8);
        out.uint32(250,8);out.bit(false); // StringValue ID250, raw x86 nine-bit ID.
        out.bit(false); // Per-instance lifetime flag, meaning not yet claimed.
        const std::string name="RccServerToken";
        out.bit(false);out.uint32(0x82,8);out.uint32(static_cast<uint32_t>(name.size()),32);string(out,name);
        out.bit(false);out.uint32(0x81,8);out.uint32(static_cast<uint32_t>(nonce.size()),32);string(out,nonce);
        out.bit(true);out.bit(false); // Archivable=true, RobloxLocked=false.
        out.uint32(1,8);
        for(unsigned byte=0;byte<4;++byte)out.uint32((parent>>(byte*8))&255,8);
        out.uint32(0,6);return out;
    }
    BitWriter globals(bool flag0,bool flag1,const std::string& scope,const std::vector<uint32_t>& indices) const {
        if(scope.empty() || scope.size()>128 || indices.empty() || indices.size()>128)
            throw std::runtime_error("globals scope/reference bound exceeded");
        for(unsigned char c:scope) if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'))
            throw std::runtime_error("invalid owned scope");
        BitWriter output;output.uint32(0x81,8);output.bit(flag0);output.bit(flag1);
        for(size_t i=0;i<indices.size();++i) {
            output.uint32(i==0?0x81:1,8);
            if(i==0) {output.uint32(static_cast<uint32_t>(scope.size()),32);string(output,scope);}
            // Raw ReadBits/WriteBits on the exact x86 build's uint32 GUID index.
            for(unsigned byte=0;byte<4;++byte) output.uint32((indices[i]>>(8*byte))&255,8);
        }
        return output;
    }
};
}
