#!/usr/bin/env python3
"""
Find JaCoCo XML reports in a multi-module Maven project.
"""

import os
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

def parse_args():
    parser = argparse.ArgumentParser(description='Find JaCoCo reports')
    parser.add_argument('--base-dir', type=str, default='.',
                      help='Base directory to search from')
    return parser.parse_args()

def find_jacoco_reports(base_dir='.'):
    """Find all JaCoCo XML reports recursively."""
    print(f"Searching for JaCoCo reports in {os.path.abspath(base_dir)}")
    
    # Common locations for JaCoCo reports
    common_patterns = [
        "**/target/site/jacoco/jacoco.xml",
        "**/target/site/jacoco-aggregate/jacoco.xml",
        "**/target/site/jacoco-it/jacoco.xml",
        "**/build/reports/jacoco/test/jacocoTestReport.xml",
        "**/jacoco.xml"
    ]
    
    found_reports = []
    
    # Search for reports using common patterns
    for pattern in common_patterns:
        reports = list(Path(base_dir).glob(pattern))
        if reports:
            print(f"Found {len(reports)} reports matching pattern: {pattern}")
            for report in reports:
                found_reports.append(str(report))
                print(f"  - {report}")
    
    # If no reports found, search for all XML files and check if they're JaCoCo reports
    if not found_reports:
        print("No reports found in common locations. Searching for all XML files...")
        xml_files = list(Path(base_dir).glob("**/*.xml"))
        
        for xml_file in xml_files:
            try:
                tree = ET.parse(str(xml_file))
                root = tree.getroot()
                # Check if it's a JaCoCo report by looking for the report element
                if root.tag == 'report' and 'name' in root.attrib:
                    found_reports.append(str(xml_file))
                    print(f"Found JaCoCo report: {xml_file}")
            except Exception:
                # Not a valid XML or not a JaCoCo report
                pass
    
    # Check if the report is valid
    valid_reports = []
    for report in found_reports:
        try:
            tree = ET.parse(report)
            root = tree.getroot()
            if root.tag == 'report' and root.findall(".//package"):
                valid_reports.append(report)
                print(f"Validated JaCoCo report: {report}")
                # Print some basic stats
                packages = root.findall(".//package")
                classes = root.findall(".//class")
                methods = root.findall(".//method")
                print(f"  - Contains: {len(packages)} packages, {len(classes)} classes, {len(methods)} methods")
            else:
                print(f"Not a valid JaCoCo report: {report}")
        except Exception as e:
            print(f"Error validating report {report}: {e}")
    
    return valid_reports

def main():
    args = parse_args()
    reports = find_jacoco_reports(args.base_dir)
    
    if reports:
        print("\nFound valid JaCoCo reports:")
        for i, report in enumerate(reports, 1):
            print(f"{i}. {report}")
    else:
        print("\nNo valid JaCoCo reports found.")
        print("\nTo generate JaCoCo reports, run:")
        print("mvn clean verify jacoco:report")

if __name__ == "__main__":
    main()