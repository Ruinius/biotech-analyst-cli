#!/usr/bin/env python3
"""
Automated Sourcing Utilities Test Suite
Runs validation tests on all fetch and summarize utilities in the utils/ directory.
Includes deep content-level assertions for JSON structures and formatted reports.
Designed for absolute Windows, CP1252, and PowerShell compatibility.
"""

import json
import os
import subprocess
import sys

# Define the test specifications with structured assertions
TEST_SUITE = [
    {
        "name": "ClinicalTrials.gov Utilities",
        "fetch_cmd": [
            sys.executable,
            "utils/fetch_clinicaltrials.py",
            "--terms",
            "Pembrolizumab",
            "--output",
            "tmp/test_clinicaltrials_out.json",
            "--limit",
            "120",
        ],
        "sum_cmd": [
            sys.executable,
            "utils/summarize_clinicaltrials.py",
            "--input",
            "tmp/test_clinicaltrials_out.json",
            "--output",
            "tmp/test_clinicaltrials_sum.txt",
        ],
        "output_json": "tmp/test_clinicaltrials_out.json",
        "output_txt": "tmp/test_clinicaltrials_sum.txt",
        "json_assertions": [
            lambda data: isinstance(data, dict),
            lambda data: len(data) == 120,
            lambda data: any("protocolSection" in study for study in data.values()),
        ],
        "txt_assertions": [
            "CLINICAL TRIALS SUMMARY REPORT",
            "Eligibility Criteria:",
            "Sponsor",
        ],
    },
    {
        "name": "PubChem BioAssay Utilities",
        "fetch_cmd": [
            sys.executable,
            "utils/fetch_pubchem.py",
            "--compound",
            "Aspirin",
            "--output",
            "tmp/test_pubchem_out.json",
        ],
        "sum_cmd": [
            sys.executable,
            "utils/summarize_pubchem.py",
            "--input",
            "tmp/test_pubchem_out.json",
            "--output",
            "tmp/test_pubchem_sum.txt",
        ],
        "output_json": "tmp/test_pubchem_out.json",
        "output_txt": "tmp/test_pubchem_sum.txt",
        "json_assertions": [
            lambda data: data.get("cid") == 2244,
            lambda data: data.get("properties", {}).get("MolecularFormula") == "C9H8O4",
            lambda data: "assays" in data,
        ],
        "txt_assertions": [
            "PUBCHEM COMPOUND & BIOASSAY SUMMARY REPORT",
            "Molecular Weight : 180.16 g/mol",
            "Selectivity Index",
            "COX1",
        ],
    },
    {
        "name": "openFDA Briefings Utilities",
        "fetch_cmd": [
            sys.executable,
            "utils/fetch_openfda.py",
            "--drug",
            "Aspirin",
            "--output",
            "tmp/test_openfda_out.json",
        ],
        "sum_cmd": [
            sys.executable,
            "utils/summarize_openfda.py",
            "--input",
            "tmp/test_openfda_out.json",
            "--output",
            "tmp/test_openfda_sum.txt",
        ],
        "output_json": "tmp/test_openfda_out.json",
        "output_txt": "tmp/test_openfda_sum.txt",
        "json_assertions": [
            lambda data: data.get("drug_name") == "Aspirin",
            lambda data: "label" in data and "events" in data,
            lambda data: data["label"]
            .get("openfda", {})
            .get("generic_name", [""])[0]
            .upper()
            == "ASPIRIN",
        ],
        "txt_assertions": [
            "OPENFDA DRUG SAFETY & LABEL SUMMARY REPORT",
            "BOXED WARNINGS (CRITICAL TOXICITIES)",
            "APPROVED INDICATIONS & USAGE",
        ],
    },
    {
        "name": "EU CTIS / ANZCTR Utilities",
        "fetch_cmd": [
            sys.executable,
            "utils/fetch_anzctr_ctis.py",
            "--term",
            "Pembrolizumab",
            "--output",
            "tmp/test_anzctr_ctis_out.json",
            "--limit",
            "120",
        ],
        "sum_cmd": [
            sys.executable,
            "utils/summarize_anzctr_ctis.py",
            "--input",
            "tmp/test_anzctr_ctis_out.json",
            "--output",
            "tmp/test_anzctr_ctis_sum.txt",
        ],
        "output_json": "tmp/test_anzctr_ctis_out.json",
        "output_txt": "tmp/test_anzctr_ctis_sum.txt",
        "json_assertions": [
            lambda data: isinstance(data.get("results"), list),
            lambda data: len(data["results"]) == 120,
            lambda data: "title" in data["results"][0],
        ],
        "txt_assertions": [
            "EU CTIS & ANZCTR CLINICAL TRIALS REPORT",
            "Total Trials Identified",
            "Title",
        ],
    },
    {
        "name": "Conference Libraries Utilities",
        "fetch_cmd": [
            sys.executable,
            "utils/fetch_conferences.py",
            "--term",
            "Pembrolizumab",
            "--output",
            "tmp/test_conferences_out.json",
            "--limit",
            "120",
        ],
        "sum_cmd": [
            sys.executable,
            "utils/summarize_conferences.py",
            "--input",
            "tmp/test_conferences_out.json",
            "--output",
            "tmp/test_conferences_sum.txt",
        ],
        "output_json": "tmp/test_conferences_out.json",
        "output_txt": "tmp/test_conferences_sum.txt",
        "json_assertions": [
            lambda data: isinstance(data.get("results"), list),
            lambda data: len(data["results"]) == 120,
            lambda data: "abstractText" in data["results"][0]
            or "title" in data["results"][0],
        ],
        "txt_assertions": [
            "MAJOR CONFERENCE ABSTRACTS & PRESENTATIONS REPORT",
            "Total Abstracts Identified",
            "Title",
        ],
    },
    {
        "name": "Chinese Registries Utilities",
        "fetch_cmd": [
            sys.executable,
            "utils/fetch_chinese_registries.py",
            "--term",
            "Pembrolizumab",
            "--output",
            "tmp/test_chinese_registries_out.json",
            "--limit",
            "120",
        ],
        "sum_cmd": [
            sys.executable,
            "utils/summarize_chinese_registries.py",
            "--input",
            "tmp/test_chinese_registries_out.json",
            "--output",
            "tmp/test_chinese_registries_sum.txt",
        ],
        "output_json": "tmp/test_chinese_registries_out.json",
        "output_txt": "tmp/test_chinese_registries_sum.txt",
        "json_assertions": [
            lambda data: isinstance(data.get("results"), list),
            lambda data: len(data["results"]) == 120,
            lambda data: "title" in data["results"][0],
        ],
        "txt_assertions": [
            "CHINESE TRIAL REGISTRY REPORT (WHO ICTRP & CHICTR)",
            "Mandarin Equivalent:",
            "Total Trials Found",
        ],
    },
    {
        "name": "Direct NMPA CDE Utilities",
        "fetch_cmd": [
            sys.executable,
            "utils/fetch_china_direct.py",
            "--term",
            "Aspirin",
            "--output",
            "tmp/test_china_direct_out.json",
        ],
        "sum_cmd": [
            sys.executable,
            "utils/summarize_china_direct.py",
            "--input",
            "tmp/test_china_direct_out.json",
            "--output",
            "tmp/test_china_direct_sum.txt",
        ],
        "output_json": "tmp/test_china_direct_out.json",
        "output_txt": "tmp/test_china_direct_sum.txt",
        "json_assertions": [
            lambda data: isinstance(data.get("records"), list),
            lambda data: len(data["records"]) > 0,
            lambda data: "acceptance_number" in data["records"][0],
        ],
        "txt_assertions": [
            "NMPA CDE DIRECT REGISTRY & IND ACCEPTANCE REPORT",
            "Applicant Company",
            "Regulatory Status",
        ],
    },
    {
        "name": "Global Patent & IP Utilities",
        "fetch_cmd": [
            sys.executable,
            "utils/fetch_ip_lens.py",
            "--term",
            "Pembrolizumab",
            "--output",
            "tmp/test_ip_lens_out.json",
        ],
        "sum_cmd": [
            sys.executable,
            "utils/summarize_ip_lens.py",
            "--input",
            "tmp/test_ip_lens_out.json",
            "--output",
            "tmp/test_ip_lens_sum.txt",
        ],
        "output_json": "tmp/test_ip_lens_out.json",
        "output_txt": "tmp/test_ip_lens_sum.txt",
        "json_assertions": [
            lambda data: isinstance(data.get("results"), list),
            lambda data: len(data["results"]) > 0,
            lambda data: "abstractText" in data["results"][0]
            or "title" in data["results"][0],
        ],
        "txt_assertions": [
            "GLOBAL PATENT & INTELLECTUAL PROPERTY (IP) REPORT",
            "Patent Office",
            "Abstract / Claims Summary:",
        ],
    },
]


def run_command(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, res.stdout, res.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def test_utility(spec):
    print("=" * 80)
    print(f"TESTING: {spec['name']}")
    print("=" * 80)

    # 1. Run Fetch command
    print(f"Running Fetcher: {' '.join(spec['fetch_cmd'])}...")
    success, out, err = run_command(spec["fetch_cmd"])
    if not success:
        print(f"[FAIL] FETCH FAILED!\nError Output:\n{err}", file=sys.stderr)
        return False

    # Check output JSON exists and is valid
    if not os.path.exists(spec["output_json"]):
        print(
            f"[ERROR] FETCH ERROR: Output file {spec['output_json']} was not created!",
            file=sys.stderr,
        )
        return False

    try:
        with open(spec["output_json"], encoding="utf-8") as f:
            data = json.load(f)

            # Content assertions for JSON
            for idx, assertion in enumerate(spec["json_assertions"], 1):
                if not assertion(data):
                    print(
                        f"[FAIL] JSON Content Assertion #{idx} failed for {spec['output_json']}!",
                        file=sys.stderr,
                    )
                    return False
    except Exception as e:
        print(
            f"[ERROR] FETCH ERROR: Failed to parse generated JSON or assertion crashed: {e}",
            file=sys.stderr,
        )
        return False

    print("[PASS] Fetcher completed successfully. Content assertions verified.")

    # 2. Run Summarizer command
    print(f"Running Summarizer: {' '.join(spec['sum_cmd'])}...")
    success, out, err = run_command(spec["sum_cmd"])
    if not success:
        print(f"[FAIL] SUMMARIZER FAILED!\nError Output:\n{err}", file=sys.stderr)
        return False

    # Check output TXT exists and is non-empty
    if not os.path.exists(spec["output_txt"]):
        print(
            f"[ERROR] SUMMARIZER ERROR: Output file {spec['output_txt']} was not created!",
            file=sys.stderr,
        )
        return False

    try:
        with open(spec["output_txt"], encoding="utf-8") as f:
            content = f.read()
            if not content:
                print(
                    f"[ERROR] SUMMARIZER ERROR: Report {spec['output_txt']} is empty!",
                    file=sys.stderr,
                )
                return False

            # Content assertions for text report
            for assertion in spec["txt_assertions"]:
                if assertion not in content:
                    print(
                        f"[FAIL] Text Assertion Failure: Keyword '{assertion}' not found in {spec['output_txt']}!",
                        file=sys.stderr,
                    )
                    return False
    except Exception as e:
        print(
            f"[ERROR] SUMMARIZER ERROR: Read or assertion failure: {e}", file=sys.stderr
        )
        return False

    print("[PASS] Summarizer completed successfully. Text content assertions verified.")
    print(f"[SUCCESS] {spec['name']} PASSED ALL TESTS.\n")
    return True


def main():
    print("RUNNING AUTOMATED SOURCING UTILITIES TEST SUITE WITH SCHEMA ASSERTIONS\n")

    # Ensure tmp directory exists
    os.makedirs("tmp", exist_ok=True)

    passed_tests = 0
    failed_tests = 0

    for spec in TEST_SUITE:
        try:
            if test_utility(spec):
                passed_tests += 1
            else:
                failed_tests += 1
        except Exception as e:
            print(
                f"[ERROR] Unexpected error testing {spec['name']}: {e}", file=sys.stderr
            )
            failed_tests += 1

    print("=" * 80)
    print("TEST SUITE SUMMARY")
    print("=" * 80)
    print(f"Total Test Configurations: {len(TEST_SUITE)}")
    print(f"[PASS] PASSED: {passed_tests}")
    print(f"[FAIL] FAILED: {failed_tests}")
    print("=" * 80)

    if failed_tests > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
