import re


def convert_to_webvtt(payload: bytes) -> str:
    encoding = "utf-16" if payload.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    text = payload.decode(encoding).replace("\r\n", "\n").replace("\r", "\n").lstrip()

    if re.match(r"WEBVTT(?:[ \t][^\n]*)?(?:\n|$)", text):
        return text

    cues = []

    if "[Events]" in text:
        fields = []

        def timestamp(value):
            hours, minutes, seconds = value.split(":")
            return f"{int(hours):02d}:{int(minutes):02d}:{float(seconds):06.3f}"

        for line in text.split("[Events]", 1)[1].splitlines():
            line = line.strip()

            if line.startswith("Format:"):
                fields = [field.strip().lower() for field in line.split(":", 1)[1].split(",")]
            elif line.startswith("Dialogue:") and fields:
                values = dict(zip(fields, line.split(":", 1)[1].strip().split(",", len(fields) - 1)))

                if not all(key in values for key in ("start", "end", "text")) or re.search(r"\{\\p[1-9]", values["text"]):
                    continue

                content = re.sub(r"\{[^}]*\}", "", values["text"]).replace(r"\N", "\n").replace(r"\n", "\n").replace(r"\h", " ")

                if content.strip():
                    cues.append(f'{timestamp(values["start"])} --> {timestamp(values["end"])}\n{content}')
    else:
        timing = re.compile(r"^(\d{2,}:[0-5]\d:[0-5]\d[,.]\d{3})\s+-->\s+(\d{2,}:[0-5]\d:[0-5]\d[,.]\d{3})$")

        for block in re.split(r"\n\s*\n", text.strip()):
            lines = block.splitlines()

            if lines and lines[0].strip().isdigit():
                lines = lines[1:]

            match = timing.fullmatch(lines[0].strip()) if lines else None

            if match:
                content = re.sub(r"\{[^}]*\}", "", "\n".join(lines[1:])).strip()

                if content:
                    cues.append(f"{match[1].replace(',', '.')} --> {match[2].replace(',', '.')}\n{content}")

    if not cues:
        raise ValueError("Subtitle response does not contain readable cues")

    return "WEBVTT\n\n" + "\n\n".join(cues) + "\n"
