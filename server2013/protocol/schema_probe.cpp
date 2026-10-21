// Offline original schema encoder for cross-language verification.
#include "../build/DescriptorData.generated.hpp"
#include <fstream>
#include <iostream>
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    const auto schema=rcc2013::ownedSchema();
    std::ofstream out(argv[1],std::ios::binary);
    out.write(reinterpret_cast<const char*>(schema.bytes().data()),schema.bytes().size());out.close();
    if(!out)return 1;
    std::cout<<"{\"bits\":"<<schema.sizeBits()<<",\"bytes\":"<<schema.bytes().size()<<"}\n";
}
