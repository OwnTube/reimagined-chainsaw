// Owned offline codec probe; does not listen or launch a Roblox process.
#include "DescriptorWriter.hpp"
#include <fstream>
#include <iostream>
#include <limits>
static uint32_t number(const std::string& text) {
    if(text.empty() || text.size()>10 || text.find_first_not_of("0123456789")!=std::string::npos)
        throw std::runtime_error("invalid input integer");
    const auto n=std::stoull(text);
    if(n>std::numeric_limits<uint32_t>::max()) throw std::runtime_error("input integer overflow");
    return static_cast<uint32_t>(n);
}
int main(int argc,char** argv) {
    try {
        if(argc!=3) throw std::runtime_error("usage: descriptor_writer_probe INPUT.tsv OUTPUT.bin");
        std::ifstream input(argv[1]);if(!input) throw std::runtime_error("input open failed");
        std::vector<rcc2013::Dictionary> tables;std::string line;
        for(unsigned t=0;t<4;++t) {
            if(!std::getline(input,line)) throw std::runtime_error("missing table count");
            const auto count=number(line);if(count>4096) throw std::runtime_error("table count exceeded");
            rcc2013::Dictionary table;
            for(uint32_t i=0;i<count;++i) {
                if(!std::getline(input,line) || line.size()>266) throw std::runtime_error("invalid entry");
                const auto tab=line.find('\t');if(tab==std::string::npos) throw std::runtime_error("missing delimiter");
                table.push_back({number(line.substr(0,tab)),line.substr(tab+1)});
            }
            tables.push_back(std::move(table));
        }
        if(std::getline(input,line)) throw std::runtime_error("trailing input");
        auto output=rcc2013::DescriptorWriter().dictionaries(tables);
        std::ofstream file(argv[2],std::ios::binary);if(!file) throw std::runtime_error("output open failed");
        file.write(reinterpret_cast<const char*>(output.bytes().data()),output.bytes().size());
        file.close();if(!file) throw std::runtime_error("output write failed");
        std::cout<<"{\"bits\":"<<output.sizeBits()<<",\"bytes\":"<<output.bytes().size()<<"}\n";
        return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
