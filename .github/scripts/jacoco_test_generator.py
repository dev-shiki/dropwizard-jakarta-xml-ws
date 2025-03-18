#!/usr/bin/env python3
"""
Improved Test Generator using JaCoCo XML Report

This script parses the JaCoCo XML report directly to find coverage gaps
and uses SambaNova to generate tests for the uncovered code.
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
import re
import json
from typing import List, Dict, Any
import subprocess
from pathlib import Path

# Import the SambaNova helper
from sambanova_api_helper import SambaNovaCoder

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate tests to improve code coverage')
    parser.add_argument('--max-classes', type=int, default=5,
                        help='Maximum number of classes to generate tests for')
    parser.add_argument('--jacoco-report', type=str, default='target/site/jacoco/jacoco.xml',
                        help='Path to the JaCoCo XML report')
    parser.add_argument('--src-dir', type=str, default='src/main/java',
                        help='Source directory for Java classes')
    parser.add_argument('--test-dir', type=str, default='src/test/java',
                        help='Directory to write generated tests to')
    parser.add_argument('--min-coverage', type=float, default=80.0,
                        help='Minimum coverage percentage threshold (default: 80.0)')
    return parser.parse_args()

def find_coverage_gaps(jacoco_path: str, min_coverage: float = 80.0) -> List[Dict[str, Any]]:
    """Find methods with low coverage from JaCoCo report."""
    print(f"Analyzing coverage report at {jacoco_path}")
    
    try:
        if not os.path.exists(jacoco_path):
            print(f"JaCoCo report not found at {jacoco_path}")
            # Try to find it
            report_files = list(Path('.').glob('**/jacoco.xml'))
            if report_files:
                jacoco_path = str(report_files[0])
                print(f"Found JaCoCo report at: {jacoco_path}")
            else:
                return []
        
        tree = ET.parse(jacoco_path)
        root = tree.getroot()
        coverage_gaps = []
        
        for package in root.findall(".//package"):
            package_name = package.attrib.get('name', '').replace('/', '.')
            
            for clazz in package.findall("class"):
                class_name = clazz.attrib.get('name', '').replace('/', '.')
                
                # Skip test classes
                if 'Test' in class_name:
                    continue
                
                # Check if class has a source file
                source_file_name = clazz.attrib.get('sourcefilename')
                if not source_file_name:
                    continue
                
                class_methods = []
                total_class_methods = 0
                covered_class_methods = 0
                
                for method in clazz.findall(".//method"):
                    method_name = method.attrib.get('name', '')
                    
                    # Skip constructors for now
                    if method_name == "<init>":
                        continue
                    
                    total_class_methods += 1
                    
                    # Find instruction coverage
                    counter = method.find("counter[@type='INSTRUCTION']")
                    if counter is not None:
                        missed = int(counter.attrib.get('missed', 0))
                        covered = int(counter.attrib.get('covered', 0))
                        total = missed + covered
                        coverage = 0 if total == 0 else (covered / total) * 100
                        
                        # Method is considered covered if it has at least one instruction covered
                        if covered > 0:
                            covered_class_methods += 1
                        
                        # Add methods with less than min_coverage
                        if coverage < min_coverage:
                            class_methods.append({
                                'method': method_name,
                                'coverage_percentage': coverage,
                                'missed_instructions': missed,
                                'priority': missed  # Higher priority for more missed instructions
                            })
                
                # Only include classes with methods that need testing
                if class_methods:
                    # Calculate overall class coverage percentage
                    class_coverage = 0 if total_class_methods == 0 else (covered_class_methods / total_class_methods) * 100
                    
                    coverage_gaps.append({
                        'package': package_name,
                        'class': class_name,
                        'source_file': source_file_name,
                        'methods': class_methods,
                        'class_coverage': class_coverage,
                        'priority': sum(m['missed_instructions'] for m in class_methods)  # Sum of all missed instructions
                    })
        
        # Sort by priority (descending)
        coverage_gaps.sort(key=lambda x: x['priority'], reverse=True)
        return coverage_gaps
        
    except Exception as e:
        print(f"Error parsing JaCoCo report: {e}")
        import traceback
        traceback.print_exc()
        return []

def find_source_file(class_name: str, src_dirs: List[str]) -> str:
    """Find the source file for a class."""
    # Extract package and class name
    parts = class_name.split('.')
    simple_name = parts[-1]
    package_path = '/'.join(parts[:-1])
    
    # Try direct path first in each source directory
    for src_dir in src_dirs:
        class_path = os.path.join(src_dir, package_path, f"{simple_name}.java")
        if os.path.exists(class_path):
            return class_path
    
    # If not found, try to find by simple name
    for src_dir in src_dirs:
        try:
            # Use find command to locate the file
            result = subprocess.run(['find', src_dir, '-name', f"{simple_name}.java"], 
                                   capture_output=True, text=True)
            if result.stdout:
                files = result.stdout.strip().split('\n')
                # Filter by package if possible
                for file in files:
                    if package_path in file:
                        return file
                # If no exact match, return the first one
                return files[0]
        except Exception as e:
            print(f"Error finding source file with find command: {e}")
    
    # If still not found, try the src/main/java and src directories
    if 'src/main/java' not in src_dirs:
        result = find_source_file(class_name, src_dirs + ['src/main/java', 'src'])
        if result:
            return result
    
    print(f"Could not find source file for {class_name}")
    return None

def get_class_source(file_path: str) -> str:
    """Read the source code from a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading source file: {e}")
        return None

def check_test_exists(class_name: str, test_dir: str) -> bool:
    """Check if a test class already exists."""
    parts = class_name.split('.')
    simple_name = parts[-1]
    package_path = '/'.join(parts[:-1])
    
    test_class_path = os.path.join(test_dir, package_path, f"{simple_name}Test.java")
    return os.path.exists(test_class_path)

def write_test_class(package_name: str, class_name: str, test_code: str, test_dir: str) -> str:
    """Write the test class to a file."""
    package_path = os.path.join(test_dir, package_name.replace('.', '/'))
    os.makedirs(package_path, exist_ok=True)
    
    simple_name = class_name.split('.')[-1]
    file_path = os.path.join(package_path, f"{simple_name}Test.java")
    
    with open(file_path, 'w') as f:
        f.write(test_code)
    
    print(f"Wrote test class to {file_path}")
    return file_path

def main():
    """Main function to generate tests."""
    args = parse_args()
    
    # Find coverage gaps
    coverage_gaps = find_coverage_gaps(args.jacoco_report, args.min_coverage)
    if not coverage_gaps:
        print("No coverage gaps found!")
        return
    
    print(f"Found {len(coverage_gaps)} classes with low coverage")
    
    # Initialize the SambaNova API helper
    sambanova = SambaNovaCoder()
    
    # Look in multiple source directories
    src_dirs = [args.src_dir]
    if 'dropwizard-jakarta-xml-ws' in os.getcwd():
        # We're in the main project directory
        src_dirs = [
            'dropwizard-jakarta-xml-ws/src/main/java',
            'dropwizard-jakarta-xml-ws-example/src/main/java',
            'src/main/java'
        ]
    
    # Process classes with the most coverage gaps, up to max_classes
    processed_count = 0
    for class_data in coverage_gaps[:args.max_classes]:
        class_name = class_data['class']
        
        # Skip classes that already have tests
        simple_class_name = class_name.split('.')[-1]
        package_name = '.'.join(class_name.split('.')[:-1])
        if check_test_exists(class_name, args.test_dir):
            print(f"Skipping {class_name} as it already has tests")
            continue
        
        print(f"\nProcessing {class_name} with {len(class_data['methods'])} methods to test")
        print(f"Class coverage: {class_data['class_coverage']:.1f}%")
        
        # Get class source
        source_file = find_source_file(class_name, src_dirs)
        if not source_file:
            print(f"Could not find source file for {class_name}, skipping")
            continue
        
        class_source = get_class_source(source_file)
        if not class_source:
            print(f"Could not read source for {class_name}, skipping")
            continue
        
        # Generate tests
        print(f"Generating tests for {class_name}...")
        try:
            # Print methods to test
            print("Methods to test:")
            for method in class_data['methods']:
                print(f"  - {method['method']} (coverage: {method['coverage_percentage']:.1f}%)")
            
            test_code = sambanova.generate_complete_test_class(
                class_source, class_name, class_data['methods']
            )
            
            if not test_code:
                print(f"No tests generated for {class_name}")
                continue
                
            # Add package declaration if missing
            if not test_code.strip().startswith("package "):
                test_code = f"package {package_name};\n\n{test_code}"
            
            # Write test class
            write_test_class(package_name, simple_class_name, test_code, args.test_dir)
            processed_count += 1
            
        except Exception as e:
            print(f"Error generating tests for {class_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\nGenerated tests for {processed_count} classes")

if __name__ == "__main__":
    main()