import argparse
import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).resolve().parent
decode_py = scripts_dir / "decode_ibl.py"
assert decode_py.exists()
h5_to_numpy_py = scripts_dir / "h5_to_numpy.py"
assert h5_to_numpy_py.exists()


grep_prefix = "[decode]:"


def decode(
    pid,
    ephys_path,
    out_path,
    roi,
    behavior,
    batch_size=None,
    max_iter=None,
    learning_rate=None,
):
    extra = []
    if batch_size is not None:
        extra.append(f"--batch_size={batch_size}")
    if max_iter is not None:
        extra.append(f"--max_iter={max_iter}")
    if learning_rate is not None:
        extra.append(f"--learning_rate={learning_rate}")
    return subprocess.run(
        [
            sys.executable,
            decode_py,
            f"--pid={pid}",
            f"--ephys_path={ephys_path}",
            f"--out_path={out_path}",
            f"--behavior={behavior}",
            f"--brain_region={roi}",
            f"--behavior={behavior}",
            *extra,
        ],
    )


def process_pid(
    pid,
    ephys_path,
    out_path,
    regions=["ca1", "dg", "lp", "po", "visa"],
    loc_suffix="",
    reg_kind="dredge",
):
    subprocess.run(
        [
            "python",
            h5_to_numpy_py,
            f"--root_path={ephys_path}",
            f"--loc-suffix={loc_suffix}",
            f"--reg-kind={reg_kind}",
        ]
    )

    print(grep_prefix, "Decoding binary choices")
    for roi in regions + ["all"]:
        decode(
            pid, ephys_path, out_path, roi, behavior="choice", max_iter=1000
        )

    print(grep_prefix, "Decoding continuous behaviors")
    for roi in regions + ["all"]:
        for behavior in ["motion_energy", "wheel_speed"]:
            decode(
                pid,
                ephys_path,
                out_path,
                roi,
                behavior=behavior,
                learning_rate="1e-3",
            )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "ephys_path", type=Path, help="Folder where h5 for this PID is"
    )
    ap.add_argument("out_path", type=Path)
    ap.add_argument("pid", type=str)
    ap.add_argument("--regions", type=str, default="ca1,dg,lp,po,visa")
    ap.add_argument("--loc-suffix", type=str, default="")
    ap.add_argument("--reg-kind", type=str, default="dredge")

    args = ap.parse_args()

    # get regions
    args.regions = args.regions.split(",")
    print("Regions:", args.regions)

    # create outdir
    args.out_path.mkdir(exist_ok=True)
    print(grep_prefix, f"Saving to {args.out_path}")

    # run the loop
    print(grep_prefix, args.pid)

    if (
        not args.ephys_path.exists()
        or not (args.ephys_path / "subtraction.h5").exists()
    ):
        print(f"{grep_prefix} No ephys for {args.pid=}. Skip.")
    else:
        process_pid(
            args.pid,
            args.ephys_path,
            args.out_path,
            regions=args.regions,
            loc_suffix=args.loc_suffix,
            reg_kind=args.reg_kind,
        )
