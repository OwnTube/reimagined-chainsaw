// Original bounded single-peer RakNet protocol-5 send queue; no engine code.
#pragma once
#include <algorithm>
#include <cstdint>
#include <deque>
#include <map>
#include <stdexcept>
#include <vector>
namespace rcc2013 {
class ReliableSender {
public:
    using Bytes=std::vector<uint8_t>;
    struct Transmission {uint32_t sequence;Bytes bytes;bool retry;};
private:
    struct Queued {Bytes frame;uint64_t ticket;bool reliable;};
    struct Pending {Bytes bytes;uint64_t ticket,sent;unsigned retries;};
    std::deque<Queued> queue_;
    std::map<uint32_t,Pending> pending_;
    std::map<uint64_t,size_t> remaining_;
    size_t resident_=0;
    uint32_t sequence_=0,reliable_=0,order_=0;
    uint16_t split_=0;
    uint64_t ticket_=0;
    static constexpr size_t budget_=1024*1024,window_=64;
    static void put(Bytes& b,uint32_t n,unsigned size,bool little=false) {
        for(unsigned i=0;i<size;++i)b.push_back(uint8_t(n>>(8*(little?i:size-i-1))));
    }
    void finished(uint64_t ticket) {
        auto it=remaining_.find(ticket);
        if(it==remaining_.end() || !it->second)throw std::runtime_error("send ticket accounting");
        if(--it->second==0)remaining_.erase(it);
    }
public:
    uint64_t enqueue(const Bytes& payload,size_t bits,unsigned mtu,bool reliable,bool ordered) {
        if(payload.empty() || payload.size()>128*1024 || !bits || (bits+7)/8!=payload.size())
            throw std::runtime_error("outbound message bound");
        if(mtu<576 || mtu>1492)throw std::runtime_error("outbound MTU bound");
        reliable=reliable||ordered;
        const size_t header=4+3+(reliable?3:0)+(ordered?4:0);
        const bool split=payload.size()>mtu-28-header;
        if(split && !reliable)throw std::runtime_error("unreliable fragmentation unsupported");
        const size_t capacity=mtu-28-header-(split?10:0);
        const size_t count=(payload.size()+capacity-1)/capacity;
        // Preflight the entire message before mutating counters or queue state.
        const size_t cost=payload.size()+count*(header+(split?10:0));
        if(count>1024 || cost>budget_-resident_ || remaining_.size()>=128)
            throw std::runtime_error("outbound queue budget");
        const auto ticket=++ticket_;
        const auto order=order_;
        if(ordered)order_=(order_+1)&0xffffff;
        const auto splitId=split_;
        if(split)++split_;
        remaining_[ticket]=count;
        for(size_t index=0,offset=0;index<count;++index) {
            const size_t length=std::min(capacity,payload.size()-offset);
            const size_t frameBits=std::min(length*8,bits-offset*8);
            Bytes frame={uint8_t((ordered?0x60:reliable?0x40:0)|(split?0x10:0))};
            put(frame,static_cast<uint32_t>(frameBits),2);
            if(reliable){put(frame,reliable_,3,true);reliable_=(reliable_+1)&0xffffff;}
            if(ordered){put(frame,order,3,true);frame.push_back(0);}
            if(split){put(frame,static_cast<uint32_t>(count),4);put(frame,splitId,2);put(frame,static_cast<uint32_t>(index),4);}
            frame.insert(frame.end(),payload.begin()+offset,payload.begin()+offset+length);
            if(frameBits%8)frame.back()&=uint8_t(255<<(8-frameBits%8));
            resident_+=frame.size()+4;
            queue_.push_back({std::move(frame),ticket,reliable});offset+=length;
        }
        return ticket;
    }
    std::vector<Transmission> poll(uint64_t now) {
        std::vector<Transmission> result;
        for(auto& entry:pending_) {
            auto& p=entry.second;
            if(now-p.sent<500)continue;
            if(p.retries>=8)throw std::runtime_error("reliable delivery retry budget exhausted");
            ++p.retries;p.sent=now;result.push_back({entry.first,p.bytes,true});
        }
        while(!queue_.empty() && pending_.size()<window_) {
            const auto seq=sequence_;sequence_=(sequence_+1)&0xffffff;
            if(pending_.count(seq))throw std::runtime_error("send sequence reuse");
            auto q=std::move(queue_.front());queue_.pop_front();
            Bytes bytes={0x84};put(bytes,seq,3,true);bytes.insert(bytes.end(),q.frame.begin(),q.frame.end());
            if(q.reliable)pending_.emplace(seq,Pending{bytes,q.ticket,now,0});
            else {resident_-=bytes.size();finished(q.ticket);}
            result.push_back({seq,std::move(bytes),false});
        }
        return result;
    }
    void acknowledge(uint32_t sequence) {
        auto it=pending_.find(sequence);
        if(it==pending_.end())return;
        resident_-=it->second.bytes.size();finished(it->second.ticket);pending_.erase(it);
    }
    bool complete(uint64_t ticket) const {return ticket && ticket<=ticket_ && remaining_.count(ticket)==0;}
    size_t pendingCount() const {return pending_.size();}
    size_t queuedCount() const {return queue_.size();}
    size_t residentBytes() const {return resident_;}
};
}
