-- The client receives world geometry only over the local engine connection.
-- No server token or owned scene is embedded in this bootstrap.
local marker = __RCC_MARKER__
local port = __RCC_PORT__
local stage = "services"
local loadCoreGui = __RCC_CORE_GUI__
print(marker .. "|CLIENT_BOOTSTRAP_STARTED")
local localOk, localConnection = pcall(function() return settings():GetFFlag("DebugLocalRccServerConnection") end)
print(marker .. "|LOCAL_RCC_FLAG|" .. tostring(localOk) .. "|" .. tostring(localConnection))
local ok, problem = pcall(function()
    local world = game:GetService("Workspace")
    local run = game:GetService("RunService")
    local network = game:GetService("NetworkClient")
    if loadCoreGui then
        local chatOk, chatProblem = pcall(function()
            game:GetService("Players"):SetChatStyle(Enum.ChatStyle.ClassicAndBubble)
        end)
        print(marker .. "|CLASSIC_CHAT_CONFIGURED|" .. tostring(chatOk) .. "|" .. tostring(chatProblem))
    end
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
    local atTarget, cameraConfigured, keyboardStart, keyboardMoved = false, false, nil, false
    if loadCoreGui then
        local capabilityOk, capability = pcall(function() return game:GetService("UserInputService").KeyboardEnabled end)
        print(marker .. "|KEYBOARD_CAPABILITY|" .. tostring(capabilityOk) .. "|" .. tostring(capability))
        local inputOk, inputProblem = pcall(function()
            local function keyReceived(key)
                if string.lower(key)=="d" then
                    print(marker .. "|KEYBOARD_INPUT_RECEIVED")
                    local player = game:GetService("Players").LocalPlayer
                    local torso = player and player.Character and player.Character:FindFirstChild("Torso")
                    local signal = world:FindFirstChild("RccJoinSignal")
                    local value = world:FindFirstChild("RccServerToken")
                    if torso and signal and value and atTarget then
                        keyboardStart = torso.Position
                        signal:FireServer(value.Value,"keyboard",0)
                    end
                end
            end
            -- Use the legacy Mouse key string API used by this era's scripts.
            -- Keep UserInputService diagnostic only: this build's KeyCode is
            -- numeric, and its enum surface differs from later clients.
            game:GetService("UserInputService").InputBegan:connect(function(input)
                print(marker .. "|INPUT_BEGAN|" .. tostring(input))
            end)
            Spawn(function()
                while not game:GetService("Players").LocalPlayer do wait() end
                game:GetService("Players").LocalPlayer:GetMouse().KeyDown:connect(keyReceived)
                print(marker .. "|LEGACY_KEYBOARD_OBSERVER_READY")
            end)
        end)
        print(marker .. "|KEYBOARD_OBSERVER_READY|" .. tostring(inputOk) .. "|" .. tostring(inputProblem))
    end
    local guiReported, guiFrames = false, 0
    run.Stepped:connect(function()
        if loadCoreGui and not guiReported then
            guiFrames = guiFrames + 1
            if guiFrames % 120 == 0 then
                local found = {}
                local function scan(parent)
                    for _, child in pairs(parent:GetChildren()) do
                        if child.Name == "ChatFrame" or child.Name == "PlayerListScreen" or child.Name == "CurrentLoadout" or child.Name == "GameMainMenu" or child.Name == "ControlFrame" then
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
                if found.ChatFrame and found.PlayerListScreen and found.CurrentLoadout and found.GameMainMenu then
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
                local floor = world:FindFirstChild("RccOwnedFloor")
                if floor then humanoid:MoveTo(torso.Position,floor) end
                atTarget = true
                print(marker .. "|CLIENT_WALK_STOPPED")
            end
            if keyboardStart and not keyboardMoved then
                local delta = torso.Position-keyboardStart
                local distance = Vector3.new(delta.X,0,delta.Z).magnitude
                if distance>2 then
                    keyboardMoved = true
                    print(marker .. "|CLIENT_KEYBOARD_MOVED|" .. tostring(distance))
                end
            end
            local camera = world.CurrentCamera
            if camera then
                if loadCoreGui then
                    if not cameraConfigured then
                        camera.CameraSubject = humanoid
                        camera.CameraType = Enum.CameraType.Follow
                        camera.CoordinateFrame = CFrame.new(torso.Position+Vector3.new(0,7,14),torso.Position)
                        camera.Focus = CFrame.new(torso.Position)
                        camera.FieldOfView = 70
                        cameraConfigured = true
                    end
                else
                camera.CameraType = Enum.CameraType.Scriptable
                camera.CoordinateFrame = CFrame.new(Vector3.new(18,14,24),Vector3.new(0,2,0))
                camera.Focus = CFrame.new(0,2,0)
                camera.FieldOfView = 50
                end
            end
        end
    end)
    stage = "PlayerConnect"
    -- This build has an explicit local-test branch for the hostname localhost.
    local player = network:PlayerConnect(0, "localhost", port, 0, 30)
    print(marker .. "|PLAYER_CONNECT_RETURNED|" .. tostring(player))
    if loadCoreGui then
        local chatOk,chatProblem = pcall(function() player:SetSuperSafeChat(false) end)
        print(marker .. "|LOCAL_CHAT_MODE|" .. tostring(chatOk) .. "|" .. tostring(chatProblem) .. "|" .. tostring(player.ChatMode))
        print(marker .. "|LOCAL_BACKPACK_PRESENT|" .. tostring(game:FindFirstChild("LocalBackpack")~=nil))
        local controllerOk,controllerProblem = pcall(function()
            local service = game:GetService("ControllerService")
            for _,controller in pairs(service:GetChildren()) do
                print(marker .. "|NATIVE_CONTROLLER|" .. controller.ClassName .. "|" .. controller.Name)
            end
        end)
        print(marker .. "|CONTROLLER_INSPECTION|" .. tostring(controllerOk) .. "|" .. tostring(controllerProblem))
        print(marker .. "|CORE_GUI_AWAITING_NATIVE_LOADER")
    end
    stage = "RunService start"
    run:Run()
    print(marker .. "|CLIENT_READY")
end)
if not ok then print(marker .. "|ERROR|stage=" .. stage .. "|" .. tostring(problem)) end
