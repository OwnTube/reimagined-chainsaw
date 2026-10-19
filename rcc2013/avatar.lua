-- Owned classic R6 fixture. Uses only the archive's bundled head mesh and face.
local avatar = Instance.new("Model")
avatar.Name = "RCC2013_ClassicPlayer"
avatar.Parent = world
local function bodyPart(name, size, position, color)
    local part = Instance.new("Part")
    part.Name = name
    part.FormFactor = Enum.FormFactor.Custom
    part.Size = size
    part.CFrame = CFrame.new(position)
    part.BrickColor = BrickColor.new(color)
    part.TopSurface = Enum.SurfaceType.Smooth
    part.BottomSurface = Enum.SurfaceType.Smooth
    part.Anchored = true
    part.CanCollide = false
    part.Parent = avatar
    return part
end
local torso = bodyPart("Torso", Vector3.new(2,2,1), Vector3.new(0,3,0), 23)
local head = bodyPart("Head", Vector3.new(2,1,1), Vector3.new(0,4.5,0), 24)
local leftArm = bodyPart("Left Arm", Vector3.new(1,2,1), Vector3.new(-1.5,3,0), 24)
local rightArm = bodyPart("Right Arm", Vector3.new(1,2,1), Vector3.new(1.5,3,0), 24)
local leftLeg = bodyPart("Left Leg", Vector3.new(1,2,1), Vector3.new(-0.5,1,0), 37)
local rightLeg = bodyPart("Right Leg", Vector3.new(1,2,1), Vector3.new(0.5,1,0), 37)
local root = bodyPart("HumanoidRootPart", Vector3.new(2,2,1), Vector3.new(0,3,0), 23)
root.Transparency = 1
local mesh = Instance.new("SpecialMesh")
mesh.MeshType = Enum.MeshType.Head
mesh.Scale = Vector3.new(1.25,1.25,1.25)
mesh.Parent = head
local face = Instance.new("Decal")
face.Name = "face"
face.Face = Enum.NormalId.Front
face.Texture = "rbxasset://textures/face.png"
face.Parent = head
local function joint(name, parent, child, offset)
    local motor = Instance.new("Motor6D")
    motor.Name = name
    motor.Part0 = parent
    motor.Part1 = child
    motor.C0 = CFrame.new(offset)
    motor.Parent = parent
end
joint("RootJoint", root, torso, Vector3.new(0,0,0))
joint("Neck", torso, head, Vector3.new(0,1.5,0))
joint("Left Shoulder", torso, leftArm, Vector3.new(-1.5,0,0))
joint("Right Shoulder", torso, rightArm, Vector3.new(1.5,0,0))
joint("Left Hip", torso, leftLeg, Vector3.new(-0.5,-2,0))
joint("Right Hip", torso, rightLeg, Vector3.new(0.5,-2,0))
local humanoid = Instance.new("Humanoid")
humanoid.NameDisplayDistance = 0
humanoid.HealthDisplayDistance = 0
humanoid.Parent = avatar
print(marker .. "|R6_READY|6 body parts|Humanoid|Motor6D|bundled head and face")
