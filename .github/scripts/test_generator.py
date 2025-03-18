#!/usr/bin/env python3
"""
Improved Test Generator for Multi-Module Projects
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

# Import the SambaNova helper (assuming it's defined)
try:
    from sambanova_api_helper import SambaNovaCoder
except ImportError:
    print("SambaNova API helper not found. Will attempt to continue without it.")
    SambaNovaCoder = None

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate tests to improve code coverage')
    parser.add_argument('--max-classes', type=int, default=5,
                        help='Maximum number of classes to generate tests for')
    parser.add_argument('--jacoco-report', type=str, default=None,
                        help='Path to the JaCoCo XML report (will auto-detect if not specified)')
    parser.add_argument('--src-dir', type=str, default=None,
                        help='Source directory for Java classes (will auto-detect if not specified)')
    parser.add_argument('--test-dir', type=str, default=None,
                        help='Directory to write generated tests to (will auto-detect if not specified)')
    parser.add_argument('--min-coverage', type=float, default=80.0,
                        help='Minimum coverage percentage threshold (default: 80.0)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output')
    parser.add_argument('--base-dir', type=str, default='../..',
                        help='Base directory (project root)')
    return parser.parse_args()

def debug_print(message, debug_enabled=False):
    """Print debug messages if debug is enabled."""
    if debug_enabled:
        print(f"DEBUG: {message}")

def find_jacoco_reports(base_dir='.', debug=False):
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
    
    # Remove duplicates while preserving order
    unique_reports = []
    for report in valid_reports:
        if report not in unique_reports:
            unique_reports.append(report)
    
    return unique_reports

def detect_project_structure(base_dir='.', debug=False):
    """Detect the project structure to find source and test directories."""
    print("Detecting project structure...")
    
    # Find all pom.xml files (Maven projects)
    pom_files = list(Path(base_dir).glob("**/pom.xml"))
    
    modules = []
    for pom_file in pom_files:
        try:
            with open(pom_file, 'r') as f:
                content = f.read()
                
            # Extract project name
            match = re.search(r'<artifactId>(.*?)</artifactId>', content)
            if match:
                artifact_id = match.group(1)
                
                # Determine if it's a module directory
                module_dir = str(pom_file.parent)
                
                # Find source directory
                src_main_java = os.path.join(module_dir, "src/main/java")
                src_test_java = os.path.join(module_dir, "src/test/java")
                
                if os.path.exists(src_main_java):
                    modules.append({
                        'name': artifact_id,
                        'dir': module_dir,
                        'src_dir': src_main_java,
                        'test_dir': src_test_java if os.path.exists(src_test_java) else None
                    })
                    debug_print(f"Found Maven module: {artifact_id} at {module_dir}", debug)
        except Exception as e:
            debug_print(f"Error processing POM file {pom_file}: {e}", debug)
    
    print(f"Found {len(modules)} Maven modules")
    for module in modules:
        print(f"  - {module['name']}: {module['dir']}")
    
    return modules

def find_coverage_gaps(jacoco_path: str, min_coverage: float = 80.0, debug: bool = False) -> List[Dict[str, Any]]:
    """Find methods with low coverage from JaCoCo report."""
    print(f"Analyzing coverage report at {jacoco_path}")
    
    try:
        tree = ET.parse(jacoco_path)
        root = tree.getroot()
        coverage_gaps = []
        
        for package in root.findall(".//package"):
            package_name = package.attrib.get('name', '').replace('/', '.')
            debug_print(f"Processing package: {package_name}", debug)
            
            for clazz in package.findall("class"):
                class_name = clazz.attrib.get('name', '').replace('/', '.')
                
                # Skip test classes
                if 'Test' in class_name:
                    continue
                
                debug_print(f"Processing class: {class_name}", debug)
                
                # Check if class has a source file
                source_file_name = clazz.attrib.get('sourcefilename')
                if not source_file_name:
                    debug_print(f"Class {class_name} has no source file, skipping", debug)
                    continue
                
                class_methods = []
                total_class_methods = 0
                covered_class_methods = 0
                
                for method in clazz.findall("method"):
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
                        
                        debug_print(f"Method {method_name}: coverage={coverage:.1f}%, missed={missed}, covered={covered}", debug)
                        
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
                    
                    print(f"Class {class_name}: coverage={class_coverage:.1f}%, methods={len(class_methods)}/{total_class_methods} need testing")
        
        # Sort by priority (descending)
        coverage_gaps.sort(key=lambda x: x['priority'], reverse=True)
        return coverage_gaps
        
    except Exception as e:
        print(f"Error parsing JaCoCo report: {e}")
        import traceback
        traceback.print_exc()
        return []

def find_source_file(class_name: str, modules: List[Dict], debug: bool = False) -> str:
    """Find the source file for a class using the module structure."""
    # Extract package and class name
    parts = class_name.split('.')
    simple_name = parts[-1]
    package_path = '/'.join(parts[:-1])
    
    debug_print(f"Looking for source file for {class_name}", debug)
    debug_print(f"  Package path: {package_path}", debug)
    debug_print(f"  Simple name: {simple_name}", debug)
    
    # Try direct path first in each module's source directory
    for module in modules:
        src_dir = module['src_dir']
        class_path = os.path.join(src_dir, package_path, f"{simple_name}.java")
        debug_print(f"  Checking {class_path}", debug)
        
        if os.path.exists(class_path):
            debug_print(f"  Found at {class_path}", debug)
            return class_path
    
    # If not found, try to find by simple name
    for module in modules:
        src_dir = module['src_dir']
        try:
            # Use find command to locate the file
            debug_print(f"  Using find command in {src_dir} for {simple_name}.java", debug)
            result = subprocess.run(['find', src_dir, '-name', f"{simple_name}.java"], 
                                  capture_output=True, text=True)
            if result.stdout:
                files = result.stdout.strip().split('\n')
                debug_print(f"  Found {len(files)} candidate files", debug)
                
                # Filter by package if possible
                for file in files:
                    if package_path in file:
                        debug_print(f"  Selected {file} (package match)", debug)
                        return file
                # If no exact match, return the first one
                debug_print(f"  Selected {files[0]} (first candidate)", debug)
                return files[0]
        except Exception as e:
            debug_print(f"  Error finding source file with find command: {e}", debug)
    
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

def check_test_exists(class_name: str, modules: List[Dict]) -> bool:
    """Check if a test class already exists."""
    parts = class_name.split('.')
    simple_name = parts[-1]
    package_path = '/'.join(parts[:-1])
    
    for module in modules:
        if module['test_dir']:
            test_class_path = os.path.join(module['test_dir'], package_path, f"{simple_name}Test.java")
            if os.path.exists(test_class_path):
                return True
    
    return False

def write_test_class(package_name: str, class_name: str, test_code: str, modules: List[Dict]) -> str:
    """Write the test class to a file in the appropriate module."""
    simple_name = class_name.split('.')[-1]
    
    # Try to find the right module
    target_module = None
    for module in modules:
        if module['test_dir']:
            # Look for the class in this module's source directory
            class_path = os.path.join(module['src_dir'], package_name.replace('.', '/'), f"{simple_name}.java")
            if os.path.exists(class_path):
                target_module = module
                break
    
    # If no specific module found, use the first one with a test directory
    if not target_module:
        for module in modules:
            if module['test_dir']:
                target_module = module
                break
    
    if not target_module:
        print("No suitable test directory found. Cannot write test class.")
        return None
    
    test_dir = target_module['test_dir']
    package_path = os.path.join(test_dir, package_name.replace('.', '/'))
    os.makedirs(package_path, exist_ok=True)
    
    file_path = os.path.join(package_path, f"{simple_name}Test.java")
    
    with open(file_path, 'w') as f:
        f.write(test_code)
    
    print(f"Wrote test class to {file_path}")
    return file_path

def generate_tests_with_api(class_source: str, class_name: str, methods: List[Dict], debug: bool = False):
    """Generate tests using the SambaNova API."""
    if SambaNovaCoder is None:
        print("SambaNova API helper not available. Cannot generate tests.")
        return None
    
    try:
        sambanova = SambaNovaCoder()
        return sambanova.generate_complete_test_class(class_source, class_name, methods)
    except Exception as e:
        print(f"Error generating tests: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return None

def generate_test_class_template(class_name: str, methods: List[Dict]) -> str:
    """Generate a template test class when API is not available."""
    simple_name = class_name.split('.')[-1]
    package_name = '.'.join(class_name.split('.')[:-1])
    
    template = f"""package {package_name};

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class {simple_name}Test {{

    // TODO: Add appropriate mocks
    // @Mock
    // private DependencyType dependency;
    
    private {simple_name} classUnderTest;
    
    @BeforeEach
    void setUp() {{
        // TODO: Initialize the class under test
        // classUnderTest = new {simple_name}(...);
    }}
    
"""
    
    # Add test methods
    for method in methods:
        method_name = method['method']
        template += f"""
    @Test
    void should_{method_name}_successfully() {{
        // TODO: Implement test for {method_name}
        // Given
        
        // When
        
        // Then
        
    }}
"""
    
    template += "}\n"
    return template

def main():
    """Main function to generate tests."""
    args = parse_args()
    
    # Get absolute path to base directory
    base_dir = os.path.abspath(args.base_dir)
    
    # Find JaCoCo reports
    jacoco_reports = []
    if args.jacoco_report:
        report_path = os.path.join(base_dir, args.jacoco_report) if not os.path.isabs(args.jacoco_report) else args.jacoco_report
        if os.path.exists(report_path):
            jacoco_reports = [report_path]
        else:
            print(f"Specified JaCoCo report not found: {report_path}")
    
    if not jacoco_reports:
        jacoco_reports = find_jacoco_reports(base_dir, debug=args.debug)
    
    if not jacoco_reports:
        print("No JaCoCo reports found. Cannot continue.")
        sys.exit(1)
    
    # Use the first report found
    jacoco_report = jacoco_reports[0]
    print(f"Using JaCoCo report: {jacoco_report}")
    
    # Detect project structure
    modules = detect_project_structure(base_dir, debug=args.debug)
    
    # Find coverage gaps
    coverage_gaps = find_coverage_gaps(jacoco_report, args.min_coverage, args.debug)
    if not coverage_gaps:
        print("No coverage gaps found!")
        return
    
    print(f"Found {len(coverage_gaps)} classes with low coverage")
    
    # Process classes with the most coverage gaps, up to max_classes
    processed_count = 0
    for class_data in coverage_gaps[:args.max_classes]:
        class_name = class_data['class']
        
        # Skip classes that already have tests
        simple_class_name = class_name.split('.')[-1]
        package_name = '.'.join(class_name.split('.')[:-1])
        if check_test_exists(class_name, modules):
            print(f"Skipping {class_name} as it already has tests")
            continue
        
        print(f"\nProcessing {class_name} with {len(class_data['methods'])} methods to test")
        print(f"Class coverage: {class_data['class_coverage']:.1f}%")
        
        # Get class source
        source_file = find_source_file(class_name, modules, args.debug)
        if not source_file:
            print(f"Could not find source file for {class_name}, skipping")
            continue
        
        class_source = get_class_source(source_file)
        if not class_source:
            print(f"Could not read source for {class_name}, skipping")
            continue
        
        # Generate tests
        print(f"Generating tests for {class_name}...")
        
        # Print methods to test
        print("Methods to test:")
        for method in class_data['methods']:
            print(f"  - {method['method']} (coverage: {method['coverage_percentage']:.1f}%)")
        
        # Generate tests
        test_code = generate_tests_with_api(class_source, class_name, class_data['methods'], args.debug)
        
        # If API fails, generate template
        if not test_code:
            print("API test generation failed. Generating template...")
            test_code = generate_test_class_template(class_name, class_data['methods'])
        
        # Add package declaration if missing
        if not test_code.strip().startswith("package "):
            test_code = f"package {package_name};\n\n{test_code}"
        
        # Write test class
        write_test_class(package_name, simple_class_name, test_code, modules)
        processed_count += 1
    
    print(f"\nGenerated tests for {processed_count} classes")

if __name__ == "__main__":
    main()