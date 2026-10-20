// Original RCC2013 native service. Transport only: world replication remains
// unfinished. Wire layouts were measured on our synthetic loopback fixture and
// compared with the publicly released RakNet transport documentation.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <bcrypt.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#pragma comment(lib,"Ws2_32.lib")
#pragma comment(lib,"Bcrypt.lib")

using Bytes=std::vector<unsigned char>;
namespace fs=std::filesystem;
static const Bytes magic={0,255,255,0,254,254,254,254,253,253,253,253,18,52,86,120};
static uint64_t now(){return GetTickCount64();}
static void put(Bytes& b,uint64_t n,int size,bool little=false){for(int i=0;i<size;i++)b.push_back(static_cast<unsigned char>(n>>(8*(little?i:size-i-1))));}
static uint64_t get(const Bytes& b,size_t& p,int size,bool little=false){if(p+size>b.size())throw std::runtime_error("truncated integer");uint64_t n=0;for(int i=0;i<size;i++){if(little)n|=uint64_t(b[p++])<<(8*i);else n=(n<<8)|b[p++];}return n;}
static void append(Bytes& a,const Bytes& b){a.insert(a.end(),b.begin(),b.end());}
static Bytes addr(const sockaddr_in& sa){Bytes b={4};auto ip=reinterpret_cast<const unsigned char*>(&sa.sin_addr.s_addr);for(int i=0;i<4;i++)b.push_back(ip[i]^255);put(b,ntohs(sa.sin_port),2);return b;}
static std::string escaped(const std::string& s){std::string t="\"";for(unsigned char c:s){if(c=='"'||c=='\\')t+='\\';if(c>=32&&c<127)t+=c;else t+='?';}return t+'"';}
static std::string sha256(const Bytes& bytes){BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;unsigned char digest[32];if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)throw std::runtime_error("SHA provider");if(BCryptCreateHash(alg,&hash,nullptr,0,nullptr,0,0)<0){BCryptCloseAlgorithmProvider(alg,0);throw std::runtime_error("SHA allocation");}auto status=BCryptHashData(hash,const_cast<unsigned char*>(bytes.data()),static_cast<ULONG>(bytes.size()),0);if(status>=0)status=BCryptFinishHash(hash,digest,32,0);BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(alg,0);if(status<0)throw std::runtime_error("SHA failed");std::ostringstream out;for(auto c:digest){const char* hex="0123456789abcdef";out<<hex[c>>4]<<hex[c&15];}return out.str();}

struct Frame {int reliability=0,channel=0;bool split=false;uint32_t reliable=0,order=0,count=0,index=0;uint16_t splitId=0;Bytes payload;};
struct Pending {Bytes bytes;uint64_t sent=0;int attempts=0;};
struct Assembly {uint32_t count=0,order=0;std::map<uint32_t,Bytes> chunks;size_t bytes=0;};
class Host {
    SOCKET udp=INVALID_SOCKET;
    sockaddr_in local{},peer{};
    bool hasPeer=false,connected=false;
    uint64_t guid=0;
    unsigned port=0,mtu=1492,sequence=0,reliable=0,order=0;
    std::string phase="listening";
    std::vector<std::string> events,messages;
    std::map<uint32_t,Pending> pending;
    std::set<uint32_t> seenDatagrams,seenReliable;
    std::map<int,uint32_t> expected;
    std::map<std::pair<int,uint32_t>,Frame> ordered;
    std::map<std::pair<int,uint16_t>,Assembly> assemblies;
    uint64_t received=0,sent=0;
    fs::path output;
    void event(const std::string& text){if(events.size()<256)events.push_back(text);}
    bool same(const sockaddr_in& a,const sockaddr_in& b){return a.sin_addr.s_addr==b.sin_addr.s_addr&&a.sin_port==b.sin_port;}
    void send(const Bytes& bytes){if(sendto(udp,reinterpret_cast<const char*>(bytes.data()),static_cast<int>(bytes.size()),0,reinterpret_cast<sockaddr*>(&peer),sizeof(peer))!=static_cast<int>(bytes.size()))throw std::runtime_error("UDP send failed");sent++;}
    void message(const Bytes& payload,bool reliableSend=false,bool orderedSend=false){
        if(payload.empty()||payload.size()>1200)throw std::runtime_error("unsplit send budget");
        const auto seq=sequence++&0xffffff;Bytes b={0x84};put(b,seq,3,true);b.push_back(orderedSend?0x60:reliableSend?0x40:0);put(b,payload.size()*8,2);
        if(reliableSend||orderedSend)put(b,reliable++&0xffffff,3,true);
        if(orderedSend){put(b,order++&0xffffff,3,true);b.push_back(0);}append(b,payload);
        if(reliableSend||orderedSend){if(pending.size()>=64)throw std::runtime_error("reliable send budget");pending[seq]={b,now(),0};}send(b);
    }
    void dispatch(const Bytes& body){
        if(body.empty())throw std::runtime_error("empty message");
        if(body[0]==9){
            if(phase!="offline_ready"&&phase!="accept_sent")throw std::runtime_error("connection request phase");
            if(body.size()<18||body[17]!=0)throw std::runtime_error("unsupported secure connection");
            event("connection_request_received");
            if(phase=="offline_ready"){
                Bytes reply={16};append(reply,addr(peer));put(reply,0,2);append(reply,addr(local));sockaddr_in empty{};append(reply,addr(empty));for(int i=0;i<8;i++)append(reply,addr(empty));
                reply.insert(reply.end(),body.begin()+9,body.begin()+17);put(reply,now(),8);message(reply,true,true);phase="accept_sent";event("connection_accept_sent");
            }
        }else if(body[0]==19){
            if((phase!="accept_sent"&&phase!="connected")||body.size()!=94)throw std::runtime_error("new incoming layout/phase");
            connected=true;phase="connected";event("new_incoming_connection");
        }else if(body[0]==0){
            if(body.size()!=9)throw std::runtime_error("ping time width");Bytes pong={3};pong.insert(pong.end(),body.begin()+1,body.end());put(pong,now(),8);message(pong);
        }else if(body[0]==3||body[0]==4){}
        else if(body[0]==21){phase="disconnected";event("peer_disconnected");}
        else if(messages.size()<64){std::ostringstream row;row<<"{\"id\":"<<int(body[0])<<",\"length\":"<<body.size()<<",\"sha256\":"<<escaped(sha256(body))<<"}";messages.push_back(row.str());}
    }
    void deliver(Frame f){
        if(f.reliability!=3){dispatch(f.payload);return;}
        auto key=std::make_pair(f.channel,f.order);auto& next=expected[f.channel];const auto delta=(f.order-next)&0xffffff;
        if(delta>0x7fffff)return;if(delta>512)throw std::runtime_error("ordered receive window");
        if(delta){if(ordered.size()>=512)throw std::runtime_error("ordered receive budget");ordered.emplace(key,std::move(f));return;}
        dispatch(f.payload);next=(next+1)&0xffffff;
        while(true){auto it=ordered.find({f.channel,next});if(it==ordered.end())break;dispatch(it->second.payload);ordered.erase(it);next=(next+1)&0xffffff;}
    }
    void datagram(const Bytes& b,const sockaddr_in& remote){
        if(remote.sin_addr.s_addr!=htonl(INADDR_LOOPBACK)||b.empty()||b.size()>1500)return;
        if(hasPeer&&!same(peer,remote))return;received++;
        if(b[0]==5&&b.size()>=18&&std::equal(magic.begin(),magic.end(),b.begin()+1)){
            if((phase!="listening"&&phase!="offline_1")||b[17]!=5)return;
            hasPeer=true;peer=remote;phase="offline_1";mtu=std::min<size_t>(1492,std::max<size_t>(576,b.size()+28));Bytes reply={6};append(reply,magic);put(reply,guid,8);reply.push_back(0);put(reply,mtu,2);send(reply);event("open_request_1_protocol_5");return;
        }
        if(!hasPeer)return;
        if(b[0]==7){
            if(b.size()!=34||!std::equal(magic.begin(),magic.end(),b.begin()+1)||(phase!="offline_1"&&phase!="offline_ready"))throw std::runtime_error("open request 2 layout/phase");
            size_t pos=24;mtu=static_cast<unsigned>(get(b,pos,2));if(mtu<576||mtu>1492)throw std::runtime_error("invalid MTU");phase="offline_ready";Bytes reply={8};append(reply,magic);put(reply,guid,8);append(reply,addr(peer));put(reply,mtu,2);reply.push_back(0);send(reply);event("open_request_2");return;
        }
        if((b[0]&0xc0)==0xc0){
            size_t pos=1;auto count=get(b,pos,2);if(count>128)throw std::runtime_error("ACK range count");
            for(unsigned i=0;i<count;i++){auto single=get(b,pos,1);if(single>1)throw std::runtime_error("ACK flag");auto low=get(b,pos,3,true),high=single?low:get(b,pos,3,true);if(high<low||high-low>4096)throw std::runtime_error("ACK span");for(auto it=pending.begin();it!=pending.end();){if(it->first>=low&&it->first<=high)it=pending.erase(it);else++it;}}
            if(pos!=b.size())throw std::runtime_error("trailing ACK bytes");return;
        }
        if((b[0]&0xe0)==0xa0){event("negative_ack_received");return;}
        if((b[0]&0xe0)!=0x80)return;
        size_t pos=1;auto seq=static_cast<uint32_t>(get(b,pos,3,true));Bytes ack={0xc0,0,1,1};put(ack,seq,3,true);send(ack);
        if(!seenDatagrams.insert(seq).second)return;if(seenDatagrams.size()>4096)seenDatagrams.erase(seenDatagrams.begin());
        int frames=0;
        while(pos<b.size()){
            if(++frames>256)throw std::runtime_error("frame count budget");Frame f;auto flags=get(b,pos,1);f.reliability=static_cast<int>(flags>>5);f.split=(flags&16)!=0;auto bits=get(b,pos,2);if(f.reliability>4||bits==0)throw std::runtime_error("frame flags/length");
            if(f.reliability==2||f.reliability==3||f.reliability==4)f.reliable=static_cast<uint32_t>(get(b,pos,3,true));
            if(f.reliability==1||f.reliability==4)get(b,pos,3,true);
            if(f.reliability==1||f.reliability==3||f.reliability==4){f.order=static_cast<uint32_t>(get(b,pos,3,true));f.channel=static_cast<int>(get(b,pos,1));if(f.channel>=32)throw std::runtime_error("ordered channel");}
            if(f.split){f.count=static_cast<uint32_t>(get(b,pos,4));f.splitId=static_cast<uint16_t>(get(b,pos,2));f.index=static_cast<uint32_t>(get(b,pos,4));}
            auto length=(bits+7)/8;if(pos+length>b.size())throw std::runtime_error("truncated payload");f.payload.assign(b.begin()+pos,b.begin()+pos+length);pos+=length;
            if(f.reliability>=2){if(!seenReliable.insert(f.reliable).second)continue;if(seenReliable.size()>4096)seenReliable.erase(seenReliable.begin());}
            if(f.split){
                if(f.count==0||f.count>1024||f.index>=f.count)throw std::runtime_error("split count/index");auto key=std::make_pair(f.channel,f.splitId);auto it=assemblies.find(key);
                if(it==assemblies.end()){if(assemblies.size()>=4)throw std::runtime_error("assembly budget");Assembly a;a.count=f.count;a.order=f.order;it=assemblies.emplace(key,std::move(a)).first;}
                auto& a=it->second;if(a.count!=f.count||a.order!=f.order)throw std::runtime_error("inconsistent split");if(a.chunks.count(f.index)==0){a.bytes+=f.payload.size();a.chunks.emplace(f.index,f.payload);}if(a.bytes>1024*1024)throw std::runtime_error("split byte budget");if(a.chunks.size()!=a.count)continue;
                f.payload.clear();for(uint32_t i=0;i<a.count;i++)append(f.payload,a.chunks.at(i));assemblies.erase(it);event("split_message_reassembled");
            }
            deliver(std::move(f));
        }
    }
public:
    Host(unsigned bindPort,fs::path dir):output(std::move(dir)){
        if(BCryptGenRandom(nullptr,reinterpret_cast<unsigned char*>(&guid),sizeof(guid),BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0)throw std::runtime_error("random GUID");
        udp=socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);if(udp==INVALID_SOCKET)throw std::runtime_error("UDP socket");local.sin_family=AF_INET;local.sin_addr.s_addr=htonl(INADDR_LOOPBACK);local.sin_port=htons(static_cast<u_short>(bindPort));
        if(bind(udp,reinterpret_cast<sockaddr*>(&local),sizeof(local))==SOCKET_ERROR)throw std::runtime_error("loopback bind");int len=sizeof(local);getsockname(udp,reinterpret_cast<sockaddr*>(&local),&len);port=ntohs(local.sin_port);fs::create_directories(output);save();
    }
    ~Host(){if(udp!=INVALID_SOCKET)closesocket(udp);}
    void save(){
        std::ostringstream r;r<<"{\"implementation\":\"original native C++ RCCService.exe; no Roblox engine loaded\",\"pid\":"<<GetCurrentProcessId()<<",\"port\":"<<port<<",\"phase\":"<<escaped(phase)<<",\"transport_handshake_observed\":"<<(connected?"true":"false")<<",\"game_join_validated\":false,\"world_replication_implemented\":false,\"lua_engine_implemented\":false,\"datagrams_received\":"<<received<<",\"datagrams_sent\":"<<sent<<",\"events\":[";
        bool first=true;for(const auto& e:events){if(!first)r<<',';first=false;r<<"{\"event\":"<<escaped(e)<<"}";}r<<"],\"application_messages\":[";first=true;for(const auto& m:messages){if(!first)r<<',';first=false;r<<m;}r<<"]}\n";
        auto temp=output/L"server-result.tmp",path=output/L"server-result.json";{std::ofstream stream(temp,std::ios::binary);stream<<r.str();if(!stream)throw std::runtime_error("report write");}if(!MoveFileExW(temp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("report replace");
    }
    void run(unsigned seconds){
        std::cout<<"RCC2013 native service ready on 127.0.0.1:"<<port<<"\nTransport research: world replication is unfinished.\n"<<std::flush;
        uint64_t deadline=now()+uint64_t(seconds)*1000,lastSave=0;
        while(seconds==0||now()<deadline){
            fd_set read;FD_ZERO(&read);FD_SET(udp,&read);timeval wait{0,100000};int ready=select(0,&read,nullptr,nullptr,&wait);if(ready==SOCKET_ERROR)throw std::runtime_error("UDP select");
            if(ready){unsigned char buffer[2048];sockaddr_in remote{};int len=sizeof(remote);int size=recvfrom(udp,reinterpret_cast<char*>(buffer),sizeof(buffer),0,reinterpret_cast<sockaddr*>(&remote),&len);if(size>0){try{datagram(Bytes(buffer,buffer+size),remote);}catch(const std::exception& e){event(std::string("protocol_error: ")+e.what());}}}
            for(auto& entry:pending){auto& p=entry.second;if(now()-p.sent<500)continue;if(p.attempts++>=8)throw std::runtime_error("unacknowledged control message");send(p.bytes);p.sent=now();}
            if(now()-lastSave>=100){save();lastSave=now();}
        }save();
    }
};

struct Child {
    PROCESS_INFORMATION info{};
    ~Child(){if(info.hProcess){TerminateProcess(info.hProcess,0);WaitForSingleObject(info.hProcess,5000);CloseHandle(info.hProcess);CloseHandle(info.hThread);}}
    void start(const fs::path& exe,const fs::path& content,const fs::path& data,unsigned httpPort){
        if(!fs::is_regular_file(exe))throw std::runtime_error("RCCRenderWorker.exe is missing; use --network-only for transport research");
        auto quote=[](const std::wstring& text){if(text.find(L'"')!=text.npos)throw std::runtime_error("invalid quoted path");return L"\""+text+L"\"";};
        std::wstring command=quote(exe.wstring())+L" --backend custom --content "+quote(content.wstring())+L" --data "+quote(data.wstring())+L" --port "+std::to_wstring(httpPort);STARTUPINFOW startup{};startup.cb=sizeof(startup);
        if(!CreateProcessW(exe.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,nullptr,exe.parent_path().c_str(),&startup,&info))throw std::runtime_error("render worker launch failed");
    }
};
static unsigned number(const std::wstring& text,unsigned high){size_t end=0;auto n=std::stoul(text,&end);if(end!=text.size()||n>high)throw std::runtime_error("invalid numeric option");return n;}
int wmain(int argc,wchar_t** argv){
    SetConsoleTitleW(L"RCC2013 Custom RCCService");
    WSADATA state{};if(WSAStartup(MAKEWORD(2,2),&state))return 2;
    try{
        wchar_t module[32768];if(!GetModuleFileNameW(nullptr,module,32768))throw std::runtime_error("module path");auto root=fs::path(module).parent_path();
        unsigned port=53640,http=64313,seconds=0;fs::path output=root/L"data/network",content=root/L"content",data=root/L"data/render";bool networkOnly=false;
        for(int i=1;i<argc;i++){std::wstring a=argv[i];if(a==L"-console"||a==L"--console")continue;if(a==L"--network-only"){networkOnly=true;continue;}if(a==L"--help"){std::cout<<"RCCService.exe -console [--port 53640] [--http-port 64313] [--content path] [--data path] [--output path] [--duration seconds] [--network-only]\n";WSACleanup();return 0;}if(i+1>=argc)throw std::runtime_error("missing option value");std::wstring v=argv[++i];if(a==L"--port")port=number(v,65535);else if(a==L"--http-port")http=number(v,65535);else if(a==L"--duration")seconds=number(v,180);else if(a==L"--output")output=v;else if(a==L"--content")content=v;else if(a==L"--data")data=v;else throw std::runtime_error("unknown option");}
        {Child renderer;if(!networkOnly)renderer.start(root/L"RCCRenderWorker.exe",content,data,http);Host host(port,output);host.run(seconds);}
        WSACleanup();return 0;
    }catch(const std::exception& e){std::cerr<<"RCCService: "<<e.what()<<std::endl;WSACleanup();return 1;}
}
