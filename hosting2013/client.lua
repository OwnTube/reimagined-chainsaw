-- The client receives world geometry only over the local engine connection.
-- No server token or owned scene is embedded in this bootstrap.
local marker = __RCC_MARKER__
local port = __RCC_PORT__
local stage = "services"
local loadCoreGui = __RCC_CORE_GUI__
print(marker .. "|CLIENT_BOOTSTRAP_STARTED")
local ok, problem = pcall(function()
    local world = game:GetService("Workspace")
    local run = game:GetService("RunService")
    local network = game:GetService("NetworkClient")
    stage = "connection callbacks"
    network.ConnectionAccepted:connect(function(peer, replicator)
        print(marker .. "|CONNECTION_ACCEPTED")
        local requested, errorText = pcall(function() replicator:RequestCharacter() end)
        print(marker .. "|CHARACTER_REQUEST|" .. tostring(requested) .. "|" .. tostring(errorText))
    end)
    network.ConnectionFailed:connect(function(peer, code, message)
        print(marker .. "|CONNECTION_FAILED|" .. tostring(code) .. "|" .. tostring(message))
    end)
    local first, acknowledged, walking, moved = nil, false, false, false
    local guiReported, guiFrames = false, 0
    run.Stepped:connect(function()
        if loadCoreGui and not guiReported then
            guiFrames = guiFrames + 1
            if guiFrames % 120 == 0 then
                local found = {}
                local function scan(parent)
                    for _, child in pairs(parent:GetChildren()) do
                        if child.Name == "ChatFrame" or child.Name == "PlayerList" or child.Name == "PlayerListMaster" or child.Name == "CurrentLoadout" or child.Name == "GameMainMenu" or child.Name == "ControlFrame" then
                            found[child.Name] = true
                        end
                        scan(child)
                    end
                end
                scan(game:GetService("CoreGui"))
                local names = {}
                for name in pairs(found) do table.insert(names,name) end
                table.sort(names)
                print(marker .. "|CORE_GUI_NODES|" .. table.concat(names,","))
                if found.ChatFrame and found.CurrentLoadout and found.GameMainMenu then
                    guiReported = true
                    print(marker .. "|CORE_GUI_READY")
                end
            end
        end
        local value = world:FindFirstChild("RccServerToken")
        local beacon = world:FindFirstChild("RccReplicationBeacon")
        local signal = world:FindFirstChild("RccJoinSignal")
        if value and beacon and signal and not acknowledged then
            local x = beacon.Position.X
            if first == nil then
                first = x
                print(marker .. "|REPLICATED_TOKEN|" .. value.Value)
            elseif x ~= first and math.abs(first) == 6 and math.abs(x) == 6 then
                acknowledged = true
                print(marker .. "|REPLICATED_MOVEMENT|" .. tostring(first) .. "|" .. tostring(x))
                signal:FireServer(value.Value, first, x)
            end
        end
        local player = game:GetService("Players").LocalPlayer
        local character = player and player.Character
        local torso = character and character:FindFirstChild("Torso")
        local humanoid = character and character:FindFirstChild("Humanoid")
        if torso and humanoid then
            if not walking then
                local floor = world:FindFirstChild("RccOwnedFloor")
                if floor then
                    -- Unlike later builds, this API requires its second Part.
                    humanoid:MoveTo(Vector3.new(10,3,0), floor)
                    walking = true
                    print(marker .. "|CLIENT_MOVE_REQUESTED")
                end
            end
            if not moved and torso.Position.X > 2 then
                moved = true
                print(marker .. "|CLIENT_CHARACTER_MOVED|" .. tostring(torso.Position))
            end
            local camera = world.CurrentCamera
            if camera then
                camera.CameraType = Enum.CameraType.Scriptable
                camera.CoordinateFrame = CFrame.new(Vector3.new(18,14,24),Vector3.new(0,2,0))
                camera.Focus = CFrame.new(0,2,0)
                camera.FieldOfView = 50
            end
        end
    end)
    stage = "PlayerConnect"
    -- This build has an explicit local-test branch for the hostname localhost.
    local player = network:PlayerConnect(0, "localhost", port, 0, 30)
    print(marker .. "|PLAYER_CONNECT_RETURNED|" .. tostring(player))
    if loadCoreGui then
        print(marker .. "|CORE_GUI_AWAITING_NATIVE_LOADER")
    end
    stage = "RunService start"
    run:Run()
    print(marker .. "|CLIENT_READY")
end)
if not ok then print(marker .. "|ERROR|stage=" .. stage .. "|" .. tostring(problem)) end
