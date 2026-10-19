// Standalone upstream Luau compiler/VM smoke test, not Roblox wire bytecode.
#include "Luau/Compiler.h"
#include "Luau/Bytecode.h"
#include "lua.h"
#include "lualib.h"
#include <iostream>
#include <string>

int main() {
    Luau::CompileOptions options;
    options.optimizationLevel = 2;
    options.debugLevel = 1;
    const std::string source = "local function twice(x) return x * 2 end return twice(21)";
    const std::string code = Luau::compile(source, options);
    if (code.empty() || code[0] == 0) {
        std::cerr << "Compiler failed\n";
        return 1;
    }
    lua_State* vm = luaL_newstate();
    if (!vm) return 2;
    const int loaded = luau_load(vm, "rcc-compiler-smoke", code.data(), code.size(), 0);
    const int status = loaded ? loaded : lua_pcall(vm, 0, 1, 0);
    if (status != 0) {
        std::cerr << (lua_tostring(vm, -1) ? lua_tostring(vm, -1) : "VM failed") << "\n";
        lua_close(vm);
        return 3;
    }
    const double result = lua_tonumber(vm, -1);
    std::cout << "{\"bytecode_version\":" << unsigned(static_cast<unsigned char>(code[0]))
              << ",\"declared_target\":" << LBC_VERSION_TARGET
              << ",\"compiled_bytes\":" << code.size()
              << ",\"standalone_vm_result\":" << result
              << ",\"roblox_player_acceptance_tested\":false}\n";
    lua_close(vm);
    return result == 42.0 ? 0 : 4;
}
