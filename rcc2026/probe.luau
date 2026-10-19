-- Run by windows_probe.py using Studio's documented RunScript task.
-- No network listeners, binary patches, or login modifications are installed.
local marker = "__RCC_MARKER__"
local requestRender = __RCC_RENDER__
local HttpService = game:GetService("HttpService")

local function emit(kind, data)
    print(marker .. HttpService:JSONEncode({ kind = kind, data = data }))
end

local function check(callback)
    local ok, value = pcall(callback)
    return { ok = ok, value = tostring(value) }
end

local report = {
    version = version(),
    isStudio = game:GetService("RunService"):IsStudio(),
    networkServer = check(function() return game:GetService("NetworkServer").ClassName end),
    legacyThumbnailGenerator = check(function() return game:GetService("ThumbnailGenerator").ClassName end),
    studioCapture = check(function() return game:GetService("StudioCaptureService").ClassName end),
}
emit("capabilities", report)

local function base64(data)
    local alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    local result = table.create(math.ceil(buffer.len(data) / 3))
    for offset = 0, buffer.len(data) - 1, 3 do
        local left = buffer.len(data) - offset
        local a = buffer.readu8(data, offset)
        local b = if left > 1 then buffer.readu8(data, offset + 1) else 0
        local c = if left > 2 then buffer.readu8(data, offset + 2) else 0
        local x = a * 65536 + b * 256 + c
        local i = math.floor(x / 262144) % 64 + 1
        local j = math.floor(x / 4096) % 64 + 1
        local k = math.floor(x / 64) % 64 + 1
        local l = x % 64 + 1
        table.insert(result, alphabet:sub(i, i) .. alphabet:sub(j, j)
            .. (if left > 1 then alphabet:sub(k, k) else "=")
            .. (if left > 2 then alphabet:sub(l, l) else "="))
    end
    return table.concat(result)
end

if requestRender then
    local ok, reason = pcall(function()
        local captureService = game:GetService("StudioCaptureService")
        -- This may prompt in Studio; lack of permission is reported, never bypassed.
        assert(captureService:RequestScreenshotPermissionAsync(), "Screenshot permission was not granted")
        assert(captureService:CanCaptureScreenshot(), "The active viewport cannot currently be captured")
        local capture = captureService:CaptureScreenshot({
            Position = Vector2.zero,
            CaptureSize = Vector2.new(256, 256),
            OutputSize = Vector2.new(256, 256),
            Format = Enum.StudioCaptureScreenshotFormat.PNG,
        })
        local deadline = os.clock() + 30
        while capture.BufferStatus ~= Enum.StudioCaptureBufferStatus.Ready do
            if capture.BufferStatus == Enum.StudioCaptureBufferStatus.Error then
                error(table.concat(capture:GetErrors(), "; "))
            end
            assert(os.clock() < deadline, "Screenshot buffer timed out")
            task.wait(0.1)
        end
        local data = capture:GetBuffer()
        assert(buffer.len(data) > 8 and buffer.len(data) <= 32 * 1024 * 1024, "Unexpected screenshot size")
        local encoded = base64(data)
        local index = 0
        for offset = 1, #encoded, 4096 do
            index += 1
            emit("png_chunk", { index = index, base64 = encoded:sub(offset, offset + 4095) })
        end
        emit("render_complete", { chunks = index, bytes = buffer.len(data), width = 256, height = 256 })
    end)
    if not ok then
        emit("render_failed", tostring(reason))
    end
end
emit("probe_complete", true)
