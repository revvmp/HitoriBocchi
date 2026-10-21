import base64
import hashlib
import json
import re

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from scrapers.providers import common


def parse_data(html: str) -> dict:
    match = re.search(r'\{type:"data",data:(\{)', html)

    if not match:
        raise common.ProviderError("Re:Anime player data is missing")

    source = html[match.start(1):]
    tokens = re.finditer(r'\s*("(?:\\.|[^"\\])*"|[A-Za-z_$][\w$]*|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}\[\]:,]|!0|!1)', source)
    items = []
    end = 0
    depth = 0

    for token in tokens:
        if token.start() != end:
            raise common.ProviderError("Unsupported Re:Anime player data")

        value = token[1]
        end = token.end()

        if value in ("{", "["):
            depth += 1
        elif value in ("}", "]"):
            depth -= 1

        items.append(value)

        if depth == 0:
            break

    normalized = []

    for index, value in enumerate(items):
        if index + 1 < len(items) and items[index + 1] == ":" and not value.startswith('"'):
            value = json.dumps(value)
        elif value in {"undefined", "!0", "!1"}:
            value = {"undefined": "null", "!0": "true", "!1": "false"}[value]

        normalized.append(value)

    return json.loads("".join(normalized))


def leb(data: bytes, position: int):
    value = 0
    shift = 0

    while position < len(data) and shift < 35:
        byte = data[position]
        position += 1
        value |= (byte & 127) << shift

        if not byte & 128:
            return value, position

        shift += 7

    raise common.ProviderError("Invalid Re:Anime decoder")


def decoder(wasm: bytes):
    if not wasm.startswith(b"\0asm\x01\0\0\0"):
        raise common.ProviderError("Invalid Re:Anime decoder")

    position = 8
    bodies = []

    while position < len(wasm):
        section = wasm[position]
        size, start = leb(wasm, position + 1)

        if section == 10:
            count, cursor = leb(wasm, start)

            for _ in range(count):
                length, cursor = leb(wasm, cursor)
                bodies.append(wasm[cursor:cursor + length])
                cursor += length

            break

        position = start + size

    marker = bytes([32, 2, 32, 5, 106, 45, 0, 0, 115, 33, 6])
    body = next((body for body in bodies if marker in body), None)

    if body is None:
        raise common.ProviderError("Unsupported Re:Anime decoder")

    start = body.index(marker) + len(marker)

    for end in range(start, len(body) - 4):
        if body[end:end + 3] == bytes([32, 5, 65]):
            step, cursor = leb(body, end + 3)

            if body[cursor] == 108:
                return body[start:end], step

    raise common.ProviderError("Re:Anime decoder keystream is missing")


def transform(code: bytes, value: int) -> int:
    local = value & 255
    stack = []
    index = 0

    while index < len(code):
        opcode = code[index]
        index += 1

        if opcode in (32, 33, 65):
            operand, index = leb(code, index)

            if opcode == 32:
                stack.append(local if operand == 6 else 0)
            elif opcode == 33:
                result = stack.pop()

                if operand == 6:
                    local = result & 255
            else:
                stack.append(operand)
        elif opcode in (106, 107, 113, 114, 115, 116, 118):
            right = stack.pop()
            left = stack.pop()
            operations = {106: lambda: left + right, 107: lambda: left - right, 113: lambda: left & right, 114: lambda: left | right, 115: lambda: left ^ right, 116: lambda: left << (right & 7), 118: lambda: left >> (right & 7)}
            stack.append(operations[opcode]() & 255)
        else:
            raise common.ProviderError("Unsupported Re:Anime decoder operation")

    return local


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def playlist_key(wasm: bytes) -> str:
    position = 8

    while position < len(wasm):
        section = wasm[position]
        size, start = leb(wasm, position + 1)

        if section == 11:
            count, cursor = leb(wasm, start)
            flag, cursor = leb(wasm, cursor)

            if count != 1 or flag != 0 or wasm[cursor] != 65:
                break

            offset, cursor = leb(wasm, cursor + 1)

            if wasm[cursor] != 11:
                break

            length, cursor = leb(wasm, cursor + 1)
            block = wasm[cursor:cursor + length]

            if offset == 2000 and length == 64:
                return base64.b64encode(bytes(left ^ right for left, right in zip(block[:32], block[32:]))).decode()

        position = start + size

    raise common.ProviderError("Unsupported Re:Anime playlist key")


def extract(client, embed: str):
    data = parse_data(client.get(embed, "https://reanime.to/", discovered=True).text)
    seed = data["obfuscation_seed"]
    first = seed

    for index in range(3):
        first = sha(first + str(index))

    second = first

    for index in range(3):
        second = sha(second + str(index))

    fragment_data = data["obfuscated_crypto_data"]["cd_" + first[24:32]]["ad_" + first[32:40]][0]["od_" + first[40:48]]
    fragment = base64.b64decode(fragment_data["kf_" + first[8:16]])
    iv = base64.b64decode(fragment_data["ivf_" + first[16:24]])
    key_fragment = base64.b64decode(data[second[:16] + "_" + second[16:24]])
    token = data[first[48:64] + "_" + first[56:64]]
    token_data = client.json(f"https://flixcloud.cc/api/m3u8/{token}", "https://reanime.to/")
    encrypted = base64.b64decode(token_data[sha(token + "vid")[:10]])
    token_bytes = base64.b64decode(token_data[sha(token + "key")[:10]])
    code, step = decoder(base64.b64decode(data["w_payload"]))
    seed_number = int(seed[:8], 16)
    material = bytes(transform(code, value ^ key_fragment[index] ^ token_bytes[index]) ^ ((index * step + seed_number) & 255) for index, value in enumerate(fragment))
    derived = hashlib.pbkdf2_hmac("sha256", material, seed.encode(), 1000, dklen=32)
    key = hashlib.sha256(bytes(value ^ ord(seed[index % len(seed)]) for index, value in enumerate(derived))).digest()
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plain = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    url = (unpadder.update(plain) + unpadder.finalize()).decode().strip().rstrip("\0")
    subtitles = data.get("subtitles", [])
    subtitle = common.english_subtitle(subtitles)
    return {"url": url, "referer": "https://flixcloud.cc/", "subtitle_url": subtitle, "manifest_key": playlist_key(base64.b64decode(data["w_payload"]))}
