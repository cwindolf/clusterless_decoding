import argparse
import subprocess
import sys
import time
from pathlib import Path

scripts_dir = Path(__file__).resolve().parent
decode_session_py = scripts_dir / "decode_session.py"
assert decode_session_py.exists()


srun = [
    "srun",
    "-p",
    "gen,genx",
    "-c",
    "24",
    "--mem",
    "384000",
    "-t",
    "1-0",
    "-J",
    "decode",
]


def run_pid(pid, ephys_path, out_path, regions=None, loc_suffix="", reg_kind="dredge"):
    return subprocess.Popen(
        [
            *srun,
            sys.executable,
            decode_session_py,
            str(ephys_path.resolve()),
            str(out_path.resolve()),
            pid,
            f"--loc-suffix={loc_suffix}",
            f"--reg-kind={reg_kind}",
            *(
                [f"--regions={','.join(regions)}"]
                if regions is not None
                else []
            ),
        ]
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()

    ap.add_argument("ephys_base_path", type=Path)
    ap.add_argument("out_path", type=Path)
    ap.add_argument("--pids", type=str, required=True)
    ap.add_argument("--ephys-dir-prefix", type=str, default="pid")
    ap.add_argument("--loc-suffix", type=str, default="")
    ap.add_argument("--reg-kind", type=str, default="dredge")
    ap.add_argument("--skip-done", action="store_true")

    args = ap.parse_args()

    print(sys.executable)
    print(f"{repr(args.ephys_dir_prefix)=}")

    # PID argument is as follows:
    #  - on the command line comma-separated
    #  - in a file, in one of two formats:
    #     - line-separated
    #     - lines of the form "<pid> [region1 region2 ...]"
    have_regions = False
    pids_is_file = False
    try:
        pids_is_file = Path(args.pids).exists()
    except OSError:
        # lots of pids lead to file name too long error
        pass
    if pids_is_file:
        with open(args.pids, "r") as pidfile:
            pids = []
            regions = []
            for line in pidfile.readlines():
                line = line.strip()
                if not line:
                    continue
                if "[" in line:
                    pid, rest = line.split("[")
                    pids.append(pid.strip())
                    assert rest.endswith("]")
                    rest = rest[:-1]
                    regions.append(rest.split())
                else:
                    pids.append(line)
                    regions.append(None)
            args.pids = pids
            have_regions = any(r is not None for r in regions)
    else:
        args.pids = args.pids.split(",")
    print(
        "Will run on these pids:\n",
        "- ",
        "\n - ".join(args.pids),
    )
    if have_regions:
        print("And regions:")
        print("\n - ".join(map(str, regions)))
        assert not args.skip_done  # didn't implement that logic...

    # create outdir
    args.out_path.mkdir(exist_ok=True)
    print(f"Saving to {args.out_path}")

    # run the loop
    allprocs = []
    for i, pid in enumerate(args.pids):
        ephys_path = args.ephys_base_path / f"{args.ephys_dir_prefix}{pid}"
        print(pid, ephys_path)
        print(f"{(ephys_path / 'subtraction.h5').exists()=}")

        if not ephys_path.exists():
            print(f"No ephys dir for {pid=}. Skip.")
            continue

        if args.skip_done and (args.out_path / pid / "wheel_speed" / "all").exists():
            print("Last region+behavior dir exists, skipping.")
            continue

        region = None
        if have_regions:
            region = regions[i]

        allprocs.append(
            run_pid(
                pid,
                ephys_path,
                args.out_path,
                regions=region,
                loc_suffix=args.loc_suffix,
                reg_kind=args.reg_kind,
            )
        )

    for _ in range(10):
        print("/")
        time.sleep(1)

    # check status
    prev_active = -1
    while True:
        num_active = sum(p.poll() is None for p in allprocs)
        if num_active != prev_active:
            print()
            print(
                num_active,
                "/",
                len(allprocs),
                "still going",
                end="",
                flush=True,
            )
            prev_active = num_active
        else:
            print(".", end="", flush=True)
        if not num_active:
            break
        time.sleep(60)
    print("bye")
