#!/usr/bin/env python3
"""
Test Generator Script

This script analyzes test coverage gaps in a Java project and uses
SambaNova's Qwen2.5-Coder to generate tests to improve coverage.
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
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    return parser.parse_args()

def find_coverage_gaps(jacoco_path: str) -> List[Dict[str, Any]]:
    """Find methods with low coverage from JaCoCo report."""
    print(f"Analyzing coverage report at {jacoco_path}")
    
    try:
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
                
                for method in clazz.findall(".//method"):
                    method_name = method.attrib.get('name', '')
                    
                    # Skip constructors for now
                    if method_name == "<init>":
                        continue
                    
                    # Find instruction coverage
                    counter = method.find("counter[@type='INSTRUCTION']")
                    if counter is not None:
                        missed = int(counter.attrib.get('missed', 0))
                        covered = int(counter.attrib.get('covered', 0))
                        total = missed + covered
                        coverage = 0 if total == 0 else (covered / total) * 100
                        
                        # Add methods with less than 80% coverage
                        if coverage < 80:
                            coverage_gaps.append({
                                'package': package_name,
                                'class': class_name,
                                'method': method_name,
                                'coverage_percentage': coverage,
                                'missed_instructions': missed,
                                'priority': missed  # Higher priority for more missed instructions
                            })
        
        # Sort by priority (descending)
        coverage_gaps.sort(key=lambda x: x['priority'], reverse=True)
        return coverage_gaps
        
    except Exception as e:
        print(f"Error parsing JaCoCo report: {e}")
        return []

def get_class_source(class_name: str, src_dir: str) -> str:
    """Get source code for a class."""
    class_path = os.path.join(src_dir, class_name.replace('.', '/') + '.java')
    try:
        with open(class_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Could not find source file for {class_name} at {class_path}")
        # Try to find by just the simple name as fallback
        simple_name = class_name.split('.')[-1]
        result = subprocess.run(['find', src_dir, '-name', f"{simple_name}.java"], 
                               capture_output=True, text=True)
        if result.stdout:
            filepath = result.stdout.strip().split('\n')[0]
            with open(filepath, 'r') as f:
                return f.read()
        return None

def check_test_exists(class_name: str, test_dir: str) -> bool:
    """Check if a test class already exists."""
    simple_name = class_name.split('.')[-1]
    test_class_path = os.path.join(test_dir, class_name.replace('.', '/') + 'Test.java')
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
    coverage_gaps = find_coverage_gaps(args.jacoco_report)
    if not coverage_gaps:
        print("No coverage gaps found!")
        return
    
    print(f"Found {len(coverage_gaps)} methods with low coverage")
    
    # Group coverage gaps by class
    class_methods = {}
    for gap in coverage_gaps:
        class_name = gap['class']
        if class_name not in class_methods:
            class_methods[class_name] = []
        class_methods[class_name].append(gap)
    
    # Initialize the SambaNova API helper
    sambanova = SambaNovaCoder()
    
    # Process classes with the most coverage gaps, up to max_classes
    processed_count = 0
    for class_name, methods in sorted(
        class_methods.items(), 
        key=lambda x: sum(method['priority'] for method in x[1]), 
        reverse=True
    ):
        if processed_count >= args.max_classes:
            break
        
        # Skip classes that already have tests
        simple_class_name = class_name.split('.')[-1]
        package_name = '.'.join(class_name.split('.')[:-1])
        if check_test_exists(class_name, args.test_dir):
            print(f"Skipping {class_name} as it already has tests")
            continue
        
        print(f"\nProcessing {class_name} with {len(methods)} low-coverage methods")
        
        # Get class source
        class_source = get_class_source(class_name, args.src_dir)
        if not class_source:
            print(f"Could not get source for {class_name}, skipping")
            continue
        
        # Generate tests
        print(f"Generating tests for {class_name}...")
        try:
            test_code = sambanova.generate_complete_test_class(
                class_source, class_name, methods
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
            continue
    
    print(f"\nGenerated tests for {processed_count} classes")

if __name__ == "__main__":
    main()