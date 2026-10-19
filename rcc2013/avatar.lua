-- Load the character template from the verified, locally restored deployment.
-- Proprietary models/meshes stay in vendor; this script only references them.
local models = game:GetObjects("rbxasset://fonts/character3.rbxm")
assert(#models == 1 and models[1]:IsA("Model"), "Bundled R6 template missing")
local avatar = models[1]
avatar.Name = "RCC2013_ClassicPlayer"
local parts = {
    {"Head", Vector3.new(0,4.5,0), 24},
    {"Torso", Vector3.new(0,3,0), 23, "torso"},
    {"Left Arm", Vector3.new(-1.5,3,0), 24, "leftarm"},
    {"Right Arm", Vector3.new(1.5,3,0), 24, "rightarm"},
    {"Left Leg", Vector3.new(-0.5,1,0), 37, "leftleg"},
    {"Right Leg", Vector3.new(0.5,1,0), 37, "rightleg"},
    {"HumanoidRootPart", Vector3.new(0,3,0), 23}
}
local meshCount = 0
for _, spec in ipairs(parts) do
    local part = avatar:FindFirstChild(spec[1])
    assert(part and part:IsA("BasePart"), "Missing template part " .. spec[1])
    part.CFrame = CFrame.new(spec[2])
    part.BrickColor = BrickColor.new(spec[3])
    part.Anchored = true
    part.CanCollide = false
    part.TopSurface = Enum.SurfaceType.Smooth
    part.BottomSurface = Enum.SurfaceType.Smooth
    if spec[4] then
        -- Explicit file meshes retain the dedicated body surfaces when the
        -- GUI-producing Humanoid is detached for a static thumbnail.
        for _, child in ipairs(part:GetChildren()) do
            if child:IsA("DataModelMesh") or child:IsA("Decal") then child:Destroy() end
        end
        local mesh = Instance.new("SpecialMesh")
        mesh.MeshType = Enum.MeshType.FileMesh
        mesh.MeshId = "rbxasset://fonts/" .. spec[4] .. ".mesh"
        mesh.Scale = Vector3.new(1,1,1)
        mesh.Parent = part
        assert(mesh.MeshId == "rbxasset://fonts/" .. spec[4] .. ".mesh")
        meshCount = meshCount + 1
        print(marker .. "|BODY_MESH|" .. part.Name .. "|" .. mesh.MeshId)
    end
end
avatar.HumanoidRootPart.Transparency = 1
local face = avatar.Head:FindFirstChild("face")
assert(face and face:IsA("Decal"), "Bundled character face missing")
face.Texture = "rbxasset://textures/face.png"
local humanoid = avatar:FindFirstChild("Humanoid")
assert(humanoid and humanoid:IsA("Humanoid"), "Bundled character Humanoid missing")
humanoid.Parent = nil
humanoid:Destroy()
avatar.Name = ""
avatar.Parent = world
assert(meshCount == 5 and avatar:FindFirstChild("Humanoid") == nil)
print(marker .. "|R6_READY|bundled character3.rbxm|6 body parts|bundled head and face")
print(marker .. "|BODY_MESH_READY|5 dedicated bundled body meshes")
print(marker .. "|GUI_FREE|Humanoid detached before capture")
