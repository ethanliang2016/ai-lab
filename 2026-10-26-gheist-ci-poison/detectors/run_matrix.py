#!/usr/bin/env python3
"""检出率矩阵编排器
对每个攻击变体：
1. 复制基准仓库 -> 应用变更（落地形态）
2. 生成 PR 视角的 unified diff（供 M6 AI 审查与文章留档）
3. 跑 M2 actionlint / M3 zizmor / M4 IoC / M5 通用规则
4. 汇总 matrix.json + matrix.md
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
REPO = LAB / "repo"
ATTACKS = LAB / "attacks"
RUNS = LAB / "runs"
RESULTS = LAB / "results"
TOOLS = Path.home() / ".local" / "bin"
DETECTORS = LAB / "detectors"

VARIANTS = sorted(p for p in ATTACKS.iterdir() if p.is_dir())


def apply_variant(variant_dir: Path, workdir: Path) -> dict:
    scenario = json.loads((variant_dir / "scenario.json").read_text(encoding="utf-8"))
    shutil.copytree(REPO, workdir)
    for change in scenario["changes"]:
        dst = workdir / change["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(variant_dir / change["file"], dst)
    return scenario


def make_diff(variant_dir: Path, workdir: Path) -> str:
    """用 git diff --no-index 生成 PR 视角 diff。"""
    r = subprocess.run(
        ["git", "diff", "--no-index", "--src-prefix=a/", "--dst-prefix=b/",
         str(REPO), str(workdir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.stdout


def run_actionlint(workdir: Path, changed: list) -> dict:
    targets = [str(workdir / c["path"]) for c in changed
               if ".github/workflows/" in c["path"].replace("\\", "/")]
    if not targets:
        return {"detector": "M2-actionlint", "detected": False, "raw": "no workflow files"}
    r = subprocess.run(
        [str(TOOLS / "actionlint.exe"), *targets],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    raw = (r.stdout + r.stderr).strip()
    return {"detector": "M2-actionlint", "detected": r.returncode != 0, "raw": raw}


def run_zizmor(workdir: Path, changed: list) -> dict:
    exe = TOOLS / "zizmor.exe"
    if not exe.exists():
        return {"detector": "M3-zizmor", "detected": None, "raw": "zizmor not installed"}
    targets = [str(workdir / c["path"]) for c in changed
               if ".github/workflows/" in c["path"].replace("\\", "/")]
    if not targets:
        return {"detector": "M3-zizmor", "detected": False, "raw": "no workflow files"}
    r = subprocess.run(
        [str(exe), "--offline", "--no-online-audits", "--format", "json", *targets],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    raw = (r.stdout + r.stderr).strip()
    idents = []
    detected = False
    try:
        data = json.loads(r.stdout) if r.stdout.strip() else []
        for f in data:
            sev = f.get("determinations", {}).get("severity", "")
            idents.append(f"{f.get('ident')}({sev})")
            if sev.lower() in {"high", "critical"}:
                detected = True
    except json.JSONDecodeError:
        detected = r.returncode != 0
    return {"detector": "M3-zizmor", "detected": detected,
            "idents": idents, "raw": raw}


def run_py_detector(script: str, scenario: dict, workdir: Path) -> dict:
    r = subprocess.run(
        [sys.executable, str(DETECTORS / script),
         str(workdir / "_scenario.json"), str(workdir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"detector": script, "detected": None, "raw": r.stdout + r.stderr, "error": True}


def base_control() -> dict:
    """阴性对照：对未投毒的基准仓库跑全部检出器，应为全 False。"""
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td) / "base"
        shutil.copytree(REPO, workdir)
        scenario = {
            "id": "BASE", "name": "基准仓库（未投毒）",
            "branch": "main", "commit_message": "chore: regular update",
            "changes": [
                {"path": ".github/workflows/test.yml", "action": "modify"},
                {"path": ".github/workflows/lint.yml", "action": "modify"},
                {"path": ".github/workflows/release.yml", "action": "modify"},
            ],
        }
        (workdir / "_scenario.json").write_text(
            json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
        results = [
            run_actionlint(workdir, scenario["changes"]),
            run_zizmor(workdir, scenario["changes"]),
            run_py_detector("ioc_scan.py", scenario, workdir),
            run_py_detector("generic_scan.py", scenario, workdir),
        ]
        (RUNS / "base_control.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return {r["detector"]: r["detected"] for r in results}


def main():
    RUNS.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)

    control = base_control()
    print("BASE 基准仓库（阴性对照）: "
          + " ".join(f"{k}={v}" for k, v in control.items()))

    matrix = {"BASE": {"name": "基准仓库（未投毒阴性对照）", "results": control}}

    for variant_dir in VARIANTS:
        vid = json.loads((variant_dir / "scenario.json").read_text(encoding="utf-8"))["id"]
        out_dir = RUNS / variant_dir.name
        out_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "applied"
            scenario = apply_variant(variant_dir, workdir)
            (workdir / "_scenario.json").write_text(
                json.dumps(scenario, ensure_ascii=False), encoding="utf-8")

            diff = make_diff(variant_dir, workdir)
            (out_dir / "pr.diff").write_text(diff, encoding="utf-8")

            results = [
                run_actionlint(workdir, scenario["changes"]),
                run_zizmor(workdir, scenario["changes"]),
                run_py_detector("ioc_scan.py", scenario, workdir),
                run_py_detector("generic_scan.py", scenario, workdir),
            ]
            (out_dir / "detectors_raw.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            matrix[vid] = {
                "name": scenario["name"],
                "results": {r["detector"]: r["detected"] for r in results},
            }
            print(f"{vid} {scenario['name']}: "
                  + " ".join(f"{k}={v}" for k, v in matrix[vid]["results"].items()))

    (RESULTS / "matrix.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
