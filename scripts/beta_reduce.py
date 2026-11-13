"""Reduce the BETA files to what the project uses: the nine channels of the BETA paper, single precision.

Why: the 70 original files are 5.3 GB (64 channels, double precision). The project uses nine channels, which
is 0.4 GB. This script needs numpy only (no scipy), so it can run on the computer that holds the download.
It reads MATLAB 5 files with a small reader of its own (checked against scipy.io.loadmat in the unit tests).

For each S<n>.mat it writes
  S<n>.npy   float32, (9 channels, samples, 4 blocks, 40 targets), same axis order as the original
  S<n>.json  frequency and phase table, channel names, sampling rate, shape, MD5 of the source file

ssvep.beta.load_subject reads either the original files or these reduced ones and returns the same numbers.

Usage: python scripts/beta_reduce.py --raw /path/to/12264401 --out /path/to/beta_9ch [--first 1 --last 70]
"""
import argparse
import hashlib
import json
import pathlib
import struct
import zlib

import numpy as np

CHANNELS = ("PZ", "PO3", "PO5", "PO4", "PO6", "POZ", "O1", "OZ", "O2")          # Liu et al. 2020
_TYPES = {1: "i1", 2: "u1", 3: "<i2", 4: "<u2", 5: "<i4", 6: "<u4", 7: "<f4", 9: "<f8", 12: "<i8", 13: "<u8"}
_MATRIX, _COMPRESSED, _UTF8 = 14, 15, 16
_CELL, _STRUCT, _CHAR = 1, 2, 4


def _element(buf, pos):
    """Data element that starts at pos: (type, data, position of the next element)."""
    first, second = struct.unpack_from("<II", buf, pos)
    if first >> 16:                                    # small element: type and size share the first word
        size = first >> 16
        return first & 0xFFFF, buf[pos + 4:pos + 4 + size], pos + 8
    start = pos + 8
    padded = second if first == _COMPRESSED else (second + 7) & ~7
    return first, buf[start:start + second], start + padded


def _matrix(buf):
    """Body of a miMATRIX element: (name, value). Structs become dicts, cells object arrays, chars str."""
    _, flags, pos = _element(buf, 0)
    cls = flags[0]
    _, dims, pos = _element(buf, pos)
    dims = tuple(int(d) for d in np.frombuffer(dims, "<i4"))
    _, name, pos = _element(buf, pos)
    name = bytes(name).decode()
    count = int(np.prod(dims))
    if cls == _STRUCT:
        _, length, pos = _element(buf, pos)
        length = int(np.frombuffer(length, "<i4")[0])
        _, names, pos = _element(buf, pos)
        fields = [bytes(names[i:i + length]).split(b"\0")[0].decode() for i in range(0, len(names), length)]
        items = []
        for _ in range(count):
            item = {}
            for field in fields:
                _, body, pos = _element(buf, pos)
                item[field] = _matrix(body)[1] if len(body) else None
            items.append(item)
        return name, items[0] if count == 1 else items
    if cls == _CELL:
        cells = np.empty(count, dtype=object)
        for i in range(count):
            _, body, pos = _element(buf, pos)
            cells[i] = _matrix(body)[1] if len(body) else None
        return name, cells.reshape(dims, order="F")
    kind, data, pos = _element(buf, pos)
    if cls == _CHAR:
        text = bytes(data).decode("utf8") if kind == _UTF8 else "".join(map(chr, np.frombuffer(data, _TYPES[kind])))
        return name, text
    return name, np.frombuffer(data, _TYPES[kind]).reshape(dims, order="F")


def read_mat(path):
    """Variables of a MATLAB 5 file (numeric arrays, structs, cells, strings) as a dict."""
    raw = memoryview(pathlib.Path(path).read_bytes())
    if bytes(raw[126:128]) != b"IM":
        raise ValueError(f"{path}: not a little-endian MATLAB 5 file")
    out, pos = {}, 128
    while pos < len(raw):
        kind, data, pos = _element(raw, pos)
        if kind == _COMPRESSED:
            data = memoryview(zlib.decompress(data))
            kind, data, _ = _element(data, 0)
        if kind == _MATRIX:
            name, value = _matrix(data)
            out[name] = value
    return out


def reduce_file(src, out_dir):
    src = pathlib.Path(src)
    data = read_mat(src)["data"]
    eeg, info = data["EEG"], data["suppl_info"]
    names = [str(c).strip().upper() for c in info["chan"][:, 3]]
    index = [names.index(c) for c in CHANNELS]
    small = np.ascontiguousarray(eeg[index].astype(np.float32))
    np.save(out_dir / f"{src.stem}.npy", small)
    meta = {
        "subject": str(info["sub"]), "source": src.name, "md5_source": hashlib.md5(src.read_bytes()).hexdigest(),
        "shape_original": list(eeg.shape), "dtype_original": str(eeg.dtype), "shape": list(small.shape),
        "all_finite": bool(np.isfinite(eeg).all()), "srate": float(np.ravel(info["srate"])[0]),
        "channels": list(CHANNELS), "channel_index_0based": index, "all_channels": names,
        "freqs": [float(f) for f in np.ravel(info["freqs"])], "phases": [float(p) for p in np.ravel(info["phases"])],
    }
    (out_dir / f"{src.stem}.json").write_text(json.dumps(meta))
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--last", type=int, default=70)
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for n in range(args.first, args.last + 1):
        if (out / f"S{n}.json").exists():
            continue
        meta = reduce_file(raw / f"S{n}.mat", out)
        print(f"S{n}: {meta['shape_original']} -> {meta['shape']}, finite {meta['all_finite']}", flush=True)


if __name__ == "__main__":
    main()
