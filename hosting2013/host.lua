-- Owned local test server, using unmodified Studio's legacy networking API.
local marker = MARKER
local port = PORT
local token = TOKEN
local stage = "services"
local ok, problem = pcall(function()
    local world = game:GetService("Workspace")
    local players = game:GetService("Players")
    local run = game:GetService("RunService")
    -- Establish the server role before connecting server-only RemoteEvents.
    stage = "NetworkServer creation"
    local server = game:GetService("NetworkServer")
    stage = "local authentication option"
    server:SetIsPlayerAuthenticationRequired(false)
    stage = "UDP server start"
    server:Start(port)
    print(marker .. "|NETWORK_STARTED|" .. tostring(port))
    stage = "owned scene creation"
    local function part(name, position, size, color)
        local p = Instance.new("Part")
        p.Name = name
        p.FormFactor = Enum.FormFactor.Custom
        p.Size = size
        p.CFrame = CFrame.new(position)
        p.Anchored = true
        p.BrickColor = BrickColor.new(color)
        p.TopSurface = Enum.SurfaceType.Smooth
        p.BottomSurface = Enum.SurfaceType.Smooth
        p.Parent = world
        return p
    end
    part("RccOwnedFloor", Vector3.new(0,-1,0), Vector3.new(50,2,40), 194)
    local beacon = part("RccReplicationBeacon", Vector3.new(-6,2,-8), Vector3.new(3,4,3), 21)
    local value = Instance.new("StringValue")
    value.Name = "RccServerToken"
    value.Value = token
    value.Parent = world
    local signal = Instance.new("RemoteEvent")
    signal.Name = "RccJoinSignal"
    signal.Parent = world
    stage = "server RemoteEvent callback"
    signal.OnServerEvent:connect(function(player, reply, first, second)
        if reply == token and first ~= second and math.abs(first) == 6 and math.abs(second) == 6 then
            print(marker .. "|ROUNDTRIP_CONFIRMED|" .. tostring(player.userId))
        end
    end)
    stage = "player admission callback"
    players.PlayerAdded:connect(function(player)
        print(marker .. "|PLAYER_ADDED|" .. tostring(player.userId))
        local character = game:GetObjects("rbxasset://fonts/character3.rbxm")[1]
        character.Name = "RccLocalPlayer"
        local positions = {
            ["Torso"] = Vector3.new(0,3,0), ["Head"] = Vector3.new(0,4.5,0),
            ["Left Arm"] = Vector3.new(-1.5,3,0), ["Right Arm"] = Vector3.new(1.5,3,0),
            ["Left Leg"] = Vector3.new(-0.5,1,0), ["Right Leg"] = Vector3.new(0.5,1,0),
            ["HumanoidRootPart"] = Vector3.new(0,3,0)
        }
        for name, position in pairs(positions) do
            local p = character:FindFirstChild(name)
            p.CFrame = CFrame.new(position)
            p.Anchored = false
        end
        local root, torso = character.HumanoidRootPart, character.Torso
        root.Transparency = 1
        root.CanCollide = false
        local function joint(name, parent, child, offset)
            local j = Instance.new("Motor6D")
            j.Name = name
            j.Part0 = parent
            j.Part1 = child
            j.C0 = CFrame.new(offset)
            j.Parent = parent
        end
        joint("RootJoint", root, torso, Vector3.new(0,0,0))
        joint("Neck", torso, character.Head, Vector3.new(0,1.5,0))
        joint("Left Shoulder", torso, character["Left Arm"], Vector3.new(-1.5,0,0))
        joint("Right Shoulder", torso, character["Right Arm"], Vector3.new(1.5,0,0))
        joint("Left Hip", torso, character["Left Leg"], Vector3.new(-0.5,-2,0))
        joint("Right Hip", torso, character["Right Leg"], Vector3.new(0.5,-2,0))
        character.Head.face.Texture = "rbxasset://textures/face.png"
        character.Parent = world
        player.Character = character
        print(marker .. "|CHARACTER_CREATED")
        local moved = false
        run.Stepped:connect(function()
            if not moved and torso.Position.X > 2 then
                moved = true
                print(marker .. "|SERVER_CHARACTER_MOVED|" .. tostring(torso.Position))
            end
        end)
    end)
    local frames = 0
    run.Stepped:connect(function()
        frames = frames + 1
        if frames % 120 == 0 then
            local x = math.floor(frames / 120) % 2 == 0 and -6 or 6
            beacon.CFrame = CFrame.new(x,2,-8)
        end
    end)
    stage = "RunService start"
    run:Run()
    print(marker .. "|SERVER_READY|" .. tostring(port))
end)
if not ok then print(marker .. "|ERROR|stage=" .. stage .. "|" .. tostring(problem)) end
