"""Build a signed-bootstrap compatibility loader from pinned runtime sources.

The repository contains orchestration only. Archived Roblox source is fetched
and verified separately, embedded at runtime, and never written into evidence.
"""
import json


def bootstrap(assets, base, marker):
    entries = []
    for asset,data in sorted(assets.items()):
        source = data.decode('utf-8')
        for prefix in ('http://www.roblox.com','https://www.roblox.com','http://roblox.com','https://roblox.com'):
            source = source.replace(prefix,base)
        entries.append('['+json.dumps(asset)+']=function(...)\n'+source+'\nend')
    prelude = 'local marker='+json.dumps(marker)+'\nlocal chunks={\n'+',\n'.join(entries)+'\n}\n'
    return prelude+'''
print(marker .. "|CORE_COMPAT_STARTED")
local inherited = getfenv(0)
local libraries, loading = {}, {}
local ids = {RbxGui="45284430",RbxGear="45374389",RbxUtility="60595411",RbxStamper="73157242"}
local loadLibrary
local function compile(asset, scriptObject)
    local fn = chunks[tostring(asset)]
    if not fn then error("Unpinned UI source " .. tostring(asset)) end
    local environment = setmetatable({script=scriptObject},{__index=inherited})
    environment.LoadLibrary = loadLibrary
    setfenv(fn,environment)
    return fn
end
loadLibrary = function(name)
    if libraries[name] then return libraries[name] end
    local asset = ids[name]
    if not asset then error("Unpinned UI library " .. tostring(name)) end
    if loading[name] then error("Cyclic UI library " .. tostring(name)) end
    loading[name] = true
    local value = compile(asset,nil)()
    libraries[name],loading[name] = value,nil
    print(marker .. "|CORE_LIBRARY_LOADED|" .. name)
    return value
end
local function start(asset,parent,name)
    local holder = Instance.new("LocalScript")
    holder.Name,holder.Disabled = name,true
    holder.Parent = parent
    Spawn(function()
        print(marker .. "|CORE_ASSET_STARTED|" .. tostring(asset))
        -- Lua 5.1 cannot yield through pcall. Only protect compilation; the
        -- native Spawn thread runs each archived script's waits directly.
        local ok, problem = pcall(compile,asset,holder)
        if not ok then
            print(marker .. "|CORE_ASSET_FAILED|" .. tostring(asset) .. "|" .. tostring(problem))
            return
        end
        problem()
    end)
end
local function child(parent,name)
    while not parent:FindFirstChild(name) do parent.ChildAdded:wait() end
    return parent:FindFirstChild(name)
end
local context = game:GetService("ScriptContext")
local gui = child(game:GetService("CoreGui"),"RobloxGui")
start("60595695",context,"LibraryRegistration")
start("59002209",context,"Sections")
start("36868950",gui,"ToolTip")
start("46295863",gui,"Settings")
start("39250920",gui,"MainBotChatScript")
start("48488451",gui,"PopupScript")
start("48488398",gui,"NotificationScript")
start("97188756",gui,"ChatScript")
start("107893730",gui,"PurchasePromptScript")
start("48488235",gui,"PlayerListScript")
if game:GetService("CoreGui").Version>=3 then
    start("53878047",gui,"BackpackBuilder")
    local loadout = child(gui,"CurrentLoadout")
    local backpack = child(gui,"Backpack")
    if game:GetService("CoreGui").Version>=7 then start("89449093",backpack,"BackpackManager") end
    start("89449008",backpack,"BackpackGear")
    start("53878057",loadout,"LoadoutScript")
end
print(marker .. "|CORE_COMPAT_INITIALIZED")
'''
