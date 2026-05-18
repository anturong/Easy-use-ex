import os
import re
import time


def parse_simple_tokens(text):
    if not text:
        return text

    def replace_time(match):
        format_code = match.group(1)
        try:
            return time.strftime(format_code, time.localtime(time.time()))
        except Exception:
            return match.group(0)

    text = re.sub(r"\[time\((.*?)\)\]", replace_time, text)
    text = text.replace("[time]", str(int(time.time())))
    return text


def resolve_output_dir(base_output_dir, output_path):
    base_output_dir = os.path.abspath(base_output_dir)
    output_path = parse_simple_tokens(output_path)
    output_path = str(output_path or "").strip().strip("\"'")

    if output_path.lower() in ["", "none", "."]:
        return base_output_dir
    if os.path.isabs(output_path):
        return os.path.abspath(output_path)
    return os.path.abspath(os.path.join(base_output_dir, output_path))


def normalize_stem_part(value):
    return parse_simple_tokens(str(value or "").strip())


def strip_known_extension(filename_text, expected_extension):
    filename_text = normalize_stem_part(filename_text)
    expected_extension = str(expected_extension or "").lower()

    if expected_extension and filename_text.lower().endswith(expected_extension):
        return filename_text[: -len(expected_extension)]
    return filename_text


def build_combined_stem(filename_prefix, filename_text, delimiter, default_stem):
    delimiter = str(delimiter or "_")
    prefix = normalize_stem_part(filename_prefix)
    name = normalize_stem_part(filename_text)

    if prefix and name:
        return f"{prefix}{delimiter}{name}"
    if prefix:
        return prefix
    if name:
        return name
    return normalize_stem_part(default_stem)


def build_output_file_path(
    output_dir,
    stem,
    extension,
    delimiter="_",
    digits=4,
    number_first="否",
    overwrite_mode="否",
):
    output_dir = os.path.abspath(output_dir)
    stem = normalize_stem_part(stem) or "ComfyUI"
    extension = str(extension or "")
    if extension and not extension.startswith("."):
        extension = "." + extension

    if overwrite_mode == "前缀作为文件名":
        return os.path.abspath(os.path.join(output_dir, f"{stem}{extension}"))

    delimiter = str(delimiter or "_")
    digits = max(1, int(digits))

    if number_first == "是":
        pattern = rf"(\d+){re.escape(delimiter)}{re.escape(stem)}"
    else:
        pattern = rf"{re.escape(stem)}{re.escape(delimiter)}(\d+)"

    existing_counters = [
        int(match.group(1))
        for filename in os.listdir(output_dir)
        for match in [re.search(pattern, filename)]
        if match
    ]
    existing_counters.sort(reverse=True)
    counter = existing_counters[0] + 1 if existing_counters else 1

    while True:
        if number_first == "是":
            filename = f"{counter:0{digits}}{delimiter}{stem}{extension}"
        else:
            filename = f"{stem}{delimiter}{counter:0{digits}}{extension}"

        output_file = os.path.abspath(os.path.join(output_dir, filename))
        if not os.path.exists(output_file):
            return output_file
        counter += 1
