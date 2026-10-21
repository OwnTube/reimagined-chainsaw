"""Non-replayable, bounded observations of the owned reference's ID 0x82.

Packet names/layouts from later clients are hypotheses, not a 2013 schema.
Only allowlisted symbol spans and fully parsed descriptor-table names/IDs are exported;
no ticket, globals, script, world or unknown application body is retained.
"""
import hashlib
import re
import zlib

SYMBOLS = frozenset(("Workspace", "Players", "Lighting", "ReplicatedStorage",
    "Part", "StringValue", "RemoteEvent", "Name", "Parent", "CFrame", "Position",
    "Anchored", "Size", "Value", "BrickColor", "Humanoid", "Model", "Camera",
    "OnServerEvent", "OnClientEvent", "Character", "CanCollide", "Transparency"))
MAX_BODY = 128 * 1024
MAX_EXPANDED = 512 * 1024


def shifted(data, shift):
    """View an MSB-first stream at one of eight possible byte alignments."""
    if not shift:
        return data
    return bytes(((a << shift) & 255) | (b >> (8-shift))
                 for a, b in zip(data, data[1:]))


def symbol_spans(data):
    result = []
    for shift in range(8):
        aligned = shifted(data, shift)
        for match in re.finditer(rb"[A-Za-z_][A-Za-z0-9_]{2,63}", aligned):
            name = match[0].decode("ascii")
            if name not in SYMBOLS:
                continue
            start, end = match.span()
            result.append({"symbol": name, "bit_offset": start*8+shift,
                "prefix_hex": aligned[max(0,start-6):start].hex(),
                "suffix_hex": aligned[end:end+4].hex()})
            if len(result) >= 256:
                return result
    return result


def observe(direction, payload):
    """Do not inspect any client packet or any application ID except 0x82."""
    if direction != "server_to_client" or not payload or payload[0] != 0x82:
        return None
    if not 1 < len(payload) <= MAX_BODY:
        return {"error": "ID 0x82 outside observation size bound"}
    body = payload[1:]
    result = {"id": 0x82, "length": len(payload),
              "sha256": hashlib.sha256(payload).hexdigest(),
              "layout_validated": False, "body_exported": False,
              "symbols": symbol_spans(body), "zlib_candidates": []}
    from descriptor_codec import read_tables
    result['descriptor_candidates'] = []
    result['descriptor_errors'] = {}
    for endian in ('big','little'):
        try:
            result['descriptor_candidates'].append(read_tables(payload,endian))
        except ValueError as error:
            result['descriptor_errors'][endian] = str(error)
    # A valid zlib checksum and complete bounded stream are required. We report
    # symbol fields only, even if an unrelated byte pair resembles a header.
    for offset in range(min(32, len(body)-1)):
        cmf, flg = body[offset:offset+2]
        if cmf & 15 != 8 or cmf >> 4 > 7 or (cmf*256+flg) % 31 or flg & 32:
            continue
        try:
            decoder = zlib.decompressobj()
            expanded = decoder.decompress(body[offset:], MAX_EXPANDED+1)
            if len(expanded) > MAX_EXPANDED or not decoder.eof or decoder.unused_data:
                continue
        except zlib.error:
            continue
        result["zlib_candidates"].append({"offset": offset,
            "expanded_length": len(expanded), "sha256": hashlib.sha256(expanded).hexdigest(),
            "symbols": symbol_spans(expanded)})
    return result
