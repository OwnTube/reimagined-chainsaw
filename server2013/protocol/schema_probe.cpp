// Offline original schema encoder for cross-language verification.
#include "../build/DescriptorData.generated.hpp"
#include <fstream>
#include <iostream>
int main(int argc,char** argv) {
    const bool property=argc==3 && std::string(argv[1])=="--property";
    if(argc!=2 && !property)return 2;
    const auto schema=property?rcc2013::DescriptorWriter().serviceName(0x23456789,"RCC2013_0123456789abcdef0123456789abcdef"):rcc2013::ownedSchema();
    std::ofstream out(argv[property?2:1],std::ios::binary);
    out.write(reinterpret_cast<const char*>(schema.bytes().data()),schema.bytes().size());out.close();
    if(!out)return 1;
    std::cout<<"{\"bits\":"<<schema.sizeBits()<<",\"bytes\":"<<schema.bytes().size()<<"}\n";
}
