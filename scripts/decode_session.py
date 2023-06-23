import argparse
import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).resolve().parent
decode_advi_py = scripts_dir / "decode_advi.py"
assert decode_advi_py.exists()
decode_cavi_py = scripts_dir / "decode_cavi.py"
assert decode_cavi_py.exists()
h5_to_numpy_py = scripts_dir / "h5_to_numpy.py"
assert h5_to_numpy_py.exists()


grep_prefix = "[decode]:"


def decode(
    pid,
    ephys_path,
    out_path,
    roi,
    which="cavi",
    batch_size=None,
    max_iter=None,
    learning_rate=None,
    behavior=None,
):
    if which == "cavi":
        decode_py = decode_cavi_py
    elif which == "advi":
        decode_py = decode_advi_py
    else:
        assert False
    extra = []
    if batch_size is not None:
        extra.append(f"--batch_size={batch_size}")
    if max_iter is not None:
        extra.append(f"--max_iter={max_iter}")
    if learning_rate is not None:
        extra.append(f"--learning_rate={learning_rate}")
    if behavior is not None:
        extra.append(f"--behavior={behavior}")
    return subprocess.run(
        [
            sys.executable,
            decode_py,
            f"--pid={pid}",
            f"--ephys_path={ephys_path}",
            f"--out_path={out_path}",
            f"--brain_region={roi}",
            "--featurize_behavior",
            *extra,
        ],
    )


def process_pid(
    pid, ephys_path, out_path, regions=["ca1", "dg", "lp", "po", "visa"], loc_suffix="",
):
    subprocess.run(["python", h5_to_numpy_py, f"--root_path={ephys_path}", f"--loc-suffix={loc_suffix}"])

    print(grep_prefix, "Decoding binary choices")
    for roi in regions:
        decode(pid, ephys_path, out_path, roi, max_iter=3)
    decode(
        pid,
        ephys_path,
        out_path,
        "all",
        behavior="choice",
        which="advi",
        batch_size=1,
        learning_rate="1e-2",
    )

    print(grep_prefix, "Decoding continuous behaviors")
    for roi in regions + ["all"]:
        for behavior in ["motion_energy", "wheel_speed"]:
            decode(
                pid,
                ephys_path,
                out_path,
                roi,
                which="advi",
                behavior=behavior,
                batch_size=6,
                learning_rate="1e-3",
            )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()

    ap.add_argument("ephys_path", type=Path, help="Folder where h5 for this PID is")
    ap.add_argument("out_path", type=Path)
    ap.add_argument("pid", type=str)
    ap.add_argument("--regions", type=str, default="ca1,dg,lp,po,visa")
    ap.add_argument("--loc-suffix", type=str, default="")

    args = ap.parse_args()

    # get regions
    args.regions = args.regions.split(",")
    print("Regions:", args.regions)

    # create outdir
    args.out_path.mkdir(exist_ok=True)
    print(grep_prefix, f"Saving to {args.out_path}")

    # run the loop
    print(grep_prefix, args.pid)

    if not args.ephys_path.exists() or not (args.ephys_path / "subtraction.h5").exists():
        print(f"{grep_prefix} No ephys for {args.pid=}. Skip.")
    else:
        process_pid(
            args.pid, args.ephys_path, args.out_path, regions=args.regions, loc_suffix=args.loc_suffix,
        )
