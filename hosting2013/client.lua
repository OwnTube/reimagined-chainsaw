-- The client receives world geometry only over the local engine connection.
-- No server token or owned scene is embedded in this bootstrap.
local marker = MARKER
local port = PORT
local ok, problem = pcall(function()
    local world = game:GetService("Workspace")
    local run = game:GetService("RunService")
    local network = game:GetService("NetworkClient")
    network.ConnectionAccepted:connect(function()
        print(marker .. "|CONNECTION_ACCEPTED")
    end)
    network.ConnectionFailed:connect(function(peer, code, message)
        print(marker .. "|CONNECTION_FAILED|" .. tostring(code) .. "|" .. tostring(message))
    end)
    local first, acknowledged, walking, moved = nil, false, false, false
    run.Stepped:connect(function()
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
                walking = true
                humanoid:MoveTo(Vector3.new(10,3,0))
                print(marker .. "|CLIENT_MOVE_REQUESTED")
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
    local player = network:PlayerConnect(0, "127.0.0.1", port, 0, 30)
    print(marker .. "|PLAYER_CONNECT_RETURNED|" .. tostring(player))
    run:Run()
    print(marker .. "|CLIENT_READY")
end)
if not ok then print(marker .. "|ERROR|" .. tostring(problem)) end
