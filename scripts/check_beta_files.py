"""Compare the BETA files with the checksums published by figshare (standard library only).

Usage: python scripts/check_beta_files.py --raw /path/to/12264401
       python scripts/check_beta_files.py --raw /path/to/12264401 --md5sum out1.txt out2.txt   (reuse `md5sum` output)
Exit status 1 if a file is missing or differs.
"""
import argparse
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--md5sum", nargs="*", default=[], help="files written by `md5sum`, instead of hashing again")
    args = ap.parse_args()
    raw = pathlib.Path(args.raw)
    published = {}
    for line in (ROOT / "scripts" / "figshare_md5_beta.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, size, md5 = line.split()
            published[name] = (int(size), md5)
    known = {}
    for f in args.md5sum:
        for line in pathlib.Path(f).read_text().splitlines():
            md5, name = line.split()
            known[name.lstrip("*")] = md5
    bad = []
    for name, (size, md5) in published.items():
        path = raw / name
        if not path.exists():
            bad.append(f"{name}: missing")
        elif path.stat().st_size != size:
            bad.append(f"{name}: size {path.stat().st_size}, published {size}")
        elif (known.get(name) or md5_of(path)) != md5:
            bad.append(f"{name}: MD5 differs")
    print(f"BETA: {len(published) - len(bad)} of {len(published)} files identical to the published checksums")
    for b in bad:
        print("  ", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
