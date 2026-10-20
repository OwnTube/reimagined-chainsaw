-- Load the item from our actual HTTP asset-delivery endpoint.
local objects = deliveredItemObjects
assert(#objects == 1,"Expected exactly one delivered item")
local subject = objects[1]
subject.Name = ""
local count = 0
local function prepare(parent)
    if parent:IsA("BasePart") then
        parent.Anchored = true
        parent.CanCollide = false
        count = count + 1
    end
    for _, child in pairs(parent:GetChildren()) do prepare(child) end
end
prepare(subject)
assert(count == __ITEM_PARTS__,"Delivered part count changed")
subject.Parent = world
print(marker .. "|ITEM_READY|" .. tostring(count))
