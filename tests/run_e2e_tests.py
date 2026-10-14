#!/usr/bin/env python3
"""
Standalone E2E Test Runner for instajetload_bot.
Executes Tier 1, Tier 2, Tier 3, and Tier 4 test suites,
prints an ASCII summary table, exports JSON and JUnit XML reports,
and exits with code 0 on all pass.
"""

import os
import sys
import time
import json
import unittest
import xml.etree.ElementTree as ET
from typing import Dict, Any, List

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TierResultTracker(unittest.TestResult):
    """Custom TestResult tracking detailed per-test execution data."""
    def __init__(self):
        super().__init__()
        self.test_records = []
        self._start_time = None

    def startTest(self, test):
        super().startTest(test)
        self._start_time = time.time()

    def addSuccess(self, test):
        super().addSuccess(test)
        dur = time.time() - (self._start_time or time.time())
        self.test_records.append({
            "name": test.id(),
            "status": "PASSED",
            "duration": dur,
            "error": None
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        dur = time.time() - (self._start_time or time.time())
        self.test_records.append({
            "name": test.id(),
            "status": "FAILED",
            "duration": dur,
            "error": self._exc_info_to_string(err, test)
        })

    def addError(self, test, err):
        super().addError(test, err)
        dur = time.time() - (self._start_time or time.time())
        self.test_records.append({
            "name": test.id(),
            "status": "ERROR",
            "duration": dur,
            "error": self._exc_info_to_string(err, test)
        })

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        dur = time.time() - (self._start_time or time.time())
        self.test_records.append({
            "name": test.id(),
            "status": "SKIPPED",
            "duration": dur,
            "error": reason
        })


def run_tier(tier_id: str, tier_name: str, module_name: str, target_count: int) -> Dict[str, Any]:
    """Runs a single test tier and aggregates results."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module_name)

    tracker = TierResultTracker()
    start_t = time.time()

    # Capture stdout during test execution to prevent cluttering runner summary
    suite.run(tracker)

    elapsed = time.time() - start_t
    run_count = tracker.testsRun
    failed_count = len(tracker.failures) + len(tracker.errors)
    passed_count = run_count - failed_count - len(tracker.skipped)

    return {
        "tier_id": tier_id,
        "name": tier_name,
        "module": module_name,
        "target": target_count,
        "run": run_count,
        "passed": passed_count,
        "failed": failed_count,
        "skipped": len(tracker.skipped),
        "duration": elapsed,
        "records": tracker.test_records,
        "success": (failed_count == 0 and run_count >= target_count)
    }


def generate_junit_xml(results: List[Dict[str, Any]], output_path: str):
    """Generates standard JUnit XML test report."""
    testsuites = ET.Element("testsuites")
    total_tests = sum(r["run"] for r in results)
    total_failures = sum(r["failed"] for r in results)
    total_time = sum(r["duration"] for r in results)

    testsuites.set("tests", str(total_tests))
    testsuites.set("failures", str(total_failures))
    testsuites.set("time", f"{total_time:.3f}")

    for r in results:
        ts = ET.SubElement(testsuites, "testsuite")
        ts.set("name", r["name"])
        ts.set("tests", str(r["run"]))
        ts.set("failures", str(r["failed"]))
        ts.set("time", f"{r['duration']:.3f}")

        for rec in r["records"]:
            tc = ET.SubElement(ts, "testcase")
            tc.set("name", rec["name"])
            tc.set("time", f"{rec['duration']:.3f}")
            if rec["status"] in ("FAILED", "ERROR"):
                fail_elem = ET.SubElement(tc, "failure")
                fail_elem.set("message", "Test execution failed")
                fail_elem.text = rec.get("error") or "Unknown error"
            elif rec["status"] == "SKIPPED":
                skip_elem = ET.SubElement(tc, "skipped")
                skip_elem.text = rec.get("error") or "Skipped"

    tree = ET.ElementTree(testsuites)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def generate_json_report(results: List[Dict[str, Any]], output_path: str):
    """Generates machine-readable JSON test summary."""
    data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "total_run": sum(r["run"] for r in results),
            "total_passed": sum(r["passed"] for r in results),
            "total_failed": sum(r["failed"] for r in results),
            "total_duration": sum(r["duration"] for r in results),
            "all_passed": all(r["failed"] == 0 for r in results),
        },
        "tiers": [
            {
                "tier_id": r["tier_id"],
                "name": r["name"],
                "target": r["target"],
                "run": r["run"],
                "passed": r["passed"],
                "failed": r["failed"],
                "duration": r["duration"],
                "success": r["success"],
            }
            for r in results
        ],
        "details": [
            rec for r in results for rec in r["records"]
        ]
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def print_ascii_summary(results: List[Dict[str, Any]]):
    """Prints a clean ASCII summary table to stdout."""
    total_target = sum(r["target"] for r in results)
    total_run = sum(r["run"] for r in results)
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_time = sum(r["duration"] for r in results)

    border = "+========+====================================+========+========+========+========+==========+"
    sep    = "+--------+------------------------------------+--------+--------+--------+--------+----------+"

    print("\n" + border)
    print("|                   instajetload_bot E2E Test Suite Summary Result                    |")
    print(border)
    print("| Tier   | Category Name                      | Target | Run    | Passed | Failed | Status   |")
    print(sep)

    for r in results:
        status_str = "PASSED" if r["failed"] == 0 and r["run"] >= r["target"] else "FAILED"
        print(f"| {r['tier_id']:<6} | {r['name']:<34} | >= {r['target']:<3} | {r['run']:<6} | {r['passed']:<6} | {r['failed']:<6} | {status_str:<8} |")

    print(sep)
    overall_status = "PASSED" if total_failed == 0 and total_run >= total_target else "FAILED"
    print(f"| TOTAL  | Full Verification Suite (All Tiers)| >= {total_target:<3} | {total_run:<6} | {total_passed:<6} | {total_failed:<6} | {overall_status:<8} |")
    print(border)
    print(f"Execution completed in {total_time:.2f} seconds.\n")


def main():
    print("======================================================================")
    print("🚀 Starting instajetload_bot E2E Test Suite...")
    print("======================================================================")

    tiers_config = [
        ("Tier 1", "Feature Coverage (F1-F14)", "tests.test_tier1_features", 70),
        ("Tier 2", "Boundary & Corner Cases (F1-F14)", "tests.test_tier2_boundaries", 70),
        ("Tier 3", "Cross-Feature Combinations", "tests.test_tier3_combinations", 14),
        ("Tier 4", "Real-World Workload Scenarios", "tests.test_tier4_workloads", 5),
    ]

    tier_results = []
    for tier_id, name, module_name, target in tiers_config:
        print(f"▶ Running {tier_id}: {name} ({module_name})...")
        res = run_tier(tier_id, name, module_name, target)
        tier_results.append(res)
        print(f"  ✔ Completed {tier_id}: {res['passed']}/{res['run']} passed in {res['duration']:.2f}s")

    # Output Reports
    output_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(output_dir, "test-results.json")
    xml_path = os.path.join(output_dir, "test-results.xml")

    generate_json_report(tier_results, json_path)
    generate_junit_xml(tier_results, xml_path)
    print(f"\nSaved test reports:")
    print(f"  - JSON Report : {json_path}")
    print(f"  - JUnit XML   : {xml_path}")

    # Summary Display
    print_ascii_summary(tier_results)

    # Determine exit code
    all_passed = all(r["failed"] == 0 and r["run"] >= r["target"] for r in tier_results)
    if all_passed:
        print("✅ SUCCESS: 100% of E2E verification tests passed cleanly!")
        sys.exit(0)
    else:
        print("❌ FAILURE: One or more test suites failed or did not meet coverage target.")
        sys.exit(1)


if __name__ == "__main__":
    main()
