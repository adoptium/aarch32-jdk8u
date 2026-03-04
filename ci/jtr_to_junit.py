#!/usr/bin/env python3
"""Convert jtreg JTR XML files to a JUnit-compatible XML report.

jtreg 5.1 writes per-test .jtr files (in XML format when -xml is passed)
into the JTwork directory.  GitLab CI's reports/junit stanza expects a
single aggregated junit.xml.  This script walks all .jtr files found
under a given JTwork directory and writes that aggregated file.

Usage:
    python3 jtr_to_junit.py <jtwk_dir> <junit_out>

  jtwk_dir  – path to the jtreg JTwork directory
  junit_out – path where junit.xml should be written
"""

import glob
import os
import sys
import xml.etree.ElementTree as ET


def convert(jtwk_dir, junit_out):
    jtr_files = sorted(
        glob.glob(os.path.join(jtwk_dir, '**/*.jtr'), recursive=True)
    )
    tests = failures = errors = 0
    cases = []

    for jtr_file in jtr_files:
        try:
            root = ET.parse(jtr_file).getroot()
        except ET.ParseError:
            continue

        test_id    = root.get('id', jtr_file)
        status_str = root.get('status', '')
        sl = status_str.lower()
        if sl.startswith('passed'):
            status = 'passed'
        elif sl.startswith('failed'):
            status = 'failed'
            failures += 1
        else:
            status = 'error'
            errors += 1
        tests += 1

        elapsed = '0'
        props = root.find('properties')
        if props is not None:
            for p in props.findall('property'):
                if p.get('name') == 'elapsed':
                    try:
                        elapsed = str(int(p.get('value', '0')) / 1000.0)
                    except ValueError:
                        pass

        # e.g. "compiler/7179138/Test7179138_1.java"
        #   -> classname="compiler.7179138", name="Test7179138_1"
        parts = test_id.replace('.java', '').split('/')
        classname = '.'.join(parts[:-1]) if len(parts) > 1 else 'jtreg'
        name      = parts[-1]            if len(parts) > 1 else test_id

        msg = (status_str.replace('&', '&amp;')
                         .replace('"', '&quot;')
                         .replace('<', '&lt;'))
        cases.append((classname, name, elapsed, status, msg))

    os.makedirs(os.path.dirname(junit_out), exist_ok=True)
    with open(junit_out, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            f'<testsuite name="jtreg" tests="{tests}" '
            f'failures="{failures}" errors="{errors}">\n'
        )
        for classname, name, elapsed, status, msg in cases:
            f.write(
                f'  <testcase classname="{classname}" name="{name}" '
                f'time="{elapsed}">\n'
            )
            if status == 'failed':
                f.write(f'    <failure message="{msg}"/>\n')
            elif status == 'error':
                f.write(f'    <error message="{msg}"/>\n')
            f.write('  </testcase>\n')
        f.write('</testsuite>\n')

    print(
        f"junit: {tests} tests ({failures} failures, {errors} errors)"
        f" -> {junit_out}"
    )


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <jtwk_dir> <junit_out>", file=sys.stderr)
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
