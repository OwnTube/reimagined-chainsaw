-- This block runs after loading static geometry and before each native pass.
local removed = 0
local function prohibited(node)
    local name = node.ClassName
    return node:IsA("GuiObject") or name == "ScreenGui" or name == "BillboardGui"
        or name == "SurfaceGui" or name == "Humanoid" or name == "Script"
        or name == "LocalScript" or name == "ModuleScript"
end
local function strip(parent)
    for _, child in pairs(parent:GetChildren()) do
        if prohibited(child) then child:Destroy();removed=removed+1 else strip(child) end
    end
end
strip(world)
local remaining = 0
local function audit(parent)
    for _, child in pairs(parent:GetChildren()) do
        if prohibited(child) then remaining=remaining+1 end
        audit(child)
    end
end
audit(world)
assert(remaining == 0,"Subject still contains GUI, scripts, or Humanoids")
pcall(function() game:GetService("StarterGui"):SetCoreGuiEnabled(Enum.CoreGuiType.All,false) end)
pcall(function() game:GetService("Selection"):Set({}) end)
print(marker .. "|SUBJECT_GUI_CLEAN|" .. tostring(remaining) .. "|removed=" .. tostring(removed))
