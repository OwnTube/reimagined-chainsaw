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
        const bool globals=argc==4 && std::string(argv[1])=="--globals";
        if(argc!=3 && !globals) throw std::runtime_error("usage: descriptor_writer_probe [--globals] INPUT.tsv OUTPUT.bin");
        std::ifstream input(argv[globals?2:1]);if(!input) throw std::runtime_error("input open failed");
        std::vector<rcc2013::Dictionary> tables;std::string line;
        rcc2013::BitWriter output;
        if(globals) {
            if(!std::getline(input,line) || line.size()!=2 || line.find_first_not_of("01")!=std::string::npos)
                throw std::runtime_error("expected two flag bits");
            const bool flag0=line[0]=='1',flag1=line[1]=='1';
            std::string scope;if(!std::getline(input,scope) || scope.size()>128) throw std::runtime_error("invalid scope");
            if(!std::getline(input,line)) throw std::runtime_error("missing reference count");
            const auto count=number(line);if(count>128) throw std::runtime_error("reference bound exceeded");
            std::vector<uint32_t> indices;
            for(uint32_t i=0;i<count;++i) {
                if(!std::getline(input,line)) throw std::runtime_error("missing index");
                indices.push_back(number(line));
            }
            output=rcc2013::DescriptorWriter().globals(flag0,flag1,scope,indices);
        } else for(unsigned t=0;t<4;++t) {
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
        if(!globals) output=rcc2013::DescriptorWriter().dictionaries(tables);
        std::ofstream file(argv[globals?3:2],std::ios::binary);if(!file) throw std::runtime_error("output open failed");
        file.write(reinterpret_cast<const char*>(output.bytes().data()),output.bytes().size());
        file.close();if(!file) throw std::runtime_error("output write failed");
        std::cout<<"{\"bits\":"<<output.sizeBits()<<",\"bytes\":"<<output.bytes().size()<<"}\n";
        return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
