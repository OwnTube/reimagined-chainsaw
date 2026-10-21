// Offline transport tests: independent wire reader, loss/window and bit recovery.
#include "ReliableSender.hpp"
#include <cassert>
#include <iostream>
using Sender=rcc2013::ReliableSender;
using Bytes=Sender::Bytes;
static uint32_t read(const Bytes& b,size_t& p,unsigned n,bool le=false) {
    assert(p+n<=b.size());uint32_t v=0;
    for(unsigned i=0;i<n;++i)if(le)v|=uint32_t(b[p++])<<(8*i);else v=(v<<8)|b[p++];
    return v;
}
static void reconstruct(unsigned mtu,size_t length,size_t missingBits) {
    Sender sender;Bytes input(length);for(size_t i=0;i<length;++i)input[i]=uint8_t(i*37+11);
    const auto valid=length*8-missingBits;
    if(missingBits)input.back()&=uint8_t(255<<missingBits);
    auto ticket=sender.enqueue(input,valid,mtu,true,true);
    auto next=sender.enqueue(Bytes{0x81},8,mtu,true,true);
    std::map<uint32_t,Bytes> pieces;size_t recoveredBits=0;uint32_t splitId=0,count=0;
    bool sawNext=false;size_t rounds=0;
    while(!sender.complete(next)) {
        auto frames=sender.poll(rounds*100);
        assert(!frames.empty());assert(sender.pendingCount()<=64);
        // Reverse delivery order to exercise the receiver's index-based recovery.
        for(auto f=frames.rbegin();f!=frames.rend();++f) {
            assert(!f->retry && f->bytes.size()+28<=mtu);
            size_t p=0;assert(read(f->bytes,p,1)==0x84);
            assert(read(f->bytes,p,3,true)==f->sequence);
            auto flags=read(f->bytes,p,1);auto bits=read(f->bytes,p,2);
            assert((flags>>5)==3);read(f->bytes,p,3,true);
            auto order=read(f->bytes,p,3,true);assert(read(f->bytes,p,1)==0);
            if(order==1) {assert(flags==0x60 && bits==8 && f->bytes.at(p)==0x81);sawNext=true;}
            else {
                assert(order==0);
                uint32_t index=0;
                if(flags&16) {
                    auto c=read(f->bytes,p,4),id=read(f->bytes,p,2);index=read(f->bytes,p,4);
                    if(!count){count=c;splitId=id;}assert(count==c && splitId==id && index<c);
                }
                assert(f->bytes.size()-p==(bits+7)/8);
                assert(pieces.emplace(index,Bytes(f->bytes.begin()+p,f->bytes.end())).second);
                recoveredBits+=bits;
            }
            sender.acknowledge(f->sequence);sender.acknowledge(f->sequence);
        }
        assert(++rounds<100);
    }
    Bytes recovered;for(const auto& item:pieces)recovered.insert(recovered.end(),item.second.begin(),item.second.end());
    assert(sawNext && recovered==input && recoveredBits==valid && sender.complete(ticket));
    assert(sender.residentBytes()==0 && sender.pendingCount()==0 && sender.queuedCount()==0);
}
int main() {
    for(unsigned mtu:{576u,1492u})for(size_t length:{size_t(1),size_t(500),size_t(1400),size_t(40010),size_t(131072)})
        for(size_t missing:{size_t(0),size_t(5)})reconstruct(mtu,length,missing);
    Sender loss;auto ticket=loss.enqueue(Bytes(40010,0x82),40010*8,576,true,true);
    auto first=loss.poll(0);assert(first.size()==64 && loss.queuedCount()>0);
    assert(loss.poll(499).empty());auto retry=loss.poll(500);assert(retry.size()==64);
    for(size_t i=0;i<retry.size();++i)assert(retry[i].retry && retry[i].bytes==first[i].bytes);
    // ACK one lost packet: exactly one queued frame gets the freed window slot.
    loss.acknowledge(first[9].sequence);auto freed=loss.poll(501);assert(freed.size()==1 && !freed[0].retry);
    assert(!loss.complete(ticket));loss.acknowledge(0xffffff);assert(loss.pendingCount()==64);
    for(unsigned i=2;i<=8;++i)loss.poll(i*500+1);
    bool exhausted=false;try{loss.poll(4501);}catch(const std::runtime_error&){exhausted=true;}assert(exhausted);
    Sender bounded;bool rejected=false;
    try{bounded.enqueue(Bytes(1400,0),11200,576,false,false);}catch(const std::runtime_error&){rejected=true;}
    assert(rejected && bounded.residentBytes()==0);
    for(unsigned i=0;i<6;++i)bounded.enqueue(Bytes(131072,0),131072*8,1492,true,true);
    const auto before=bounded.residentBytes();rejected=false;
    try{for(unsigned i=0;i<4;++i)bounded.enqueue(Bytes(131072,0),131072*8,1492,true,true);}catch(const std::runtime_error&){rejected=true;}
    assert(rejected && bounded.residentBytes()<1024*1024 && bounded.residentBytes()>=before);
    std::cout<<"20 MTU/partial-bit reassemblies, loss/retry, window and bounded queue passed\n";
}
