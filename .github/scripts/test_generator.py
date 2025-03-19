#!/usr/bin/env python3
"""
Updated Test Generator for Jakarta XML-WS Projects
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
import subprocess
from pathlib import Path
import re

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate tests to improve code coverage')
    parser.add_argument('--max-classes', type=int, default=5,
                        help='Maximum number of classes to generate tests for')
    parser.add_argument('--jacoco-report', type=str, default=None,
                        help='Path to the JaCoCo XML report (will auto-detect if not specified)')
    parser.add_argument('--min-coverage', type=float, default=80.0,
                        help='Minimum coverage percentage threshold (default: 80.0)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output')
    parser.add_argument('--base-dir', type=str, default='.',
                        help='Base directory (project root)')
    return parser.parse_args()

def find_jacoco_reports(base_dir='.', debug=False):
    """Find all JaCoCo XML reports recursively."""
    print(f"Searching for JaCoCo reports in {os.path.abspath(base_dir)}")
    
    # Common locations for JaCoCo reports
    common_patterns = [
        "**/target/site/jacoco/jacoco.xml",
        "**/target/site/jacoco-aggregate/jacoco.xml"
    ]
    
    found_reports = []
    
    # Search for reports using common patterns
    for pattern in common_patterns:
        cmd = f"find {base_dir} -path '{pattern}'"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                reports = result.stdout.strip().split('\n')
                found_reports.extend(reports)
        except Exception as e:
            print(f"Error searching for pattern {pattern}: {e}")
    
    # Remove duplicates and check if reports are valid
    valid_reports = []
    
    for report_path in found_reports:
        if not report_path:
            continue
            
        try:
            tree = ET.parse(report_path)
            root = tree.getroot()
            if root.tag == 'report' and root.findall(".//package"):
                valid_reports.append(report_path)
                print(f"Validated JaCoCo report: {report_path}")
                # Print some basic stats
                packages = root.findall(".//package")
                classes = root.findall(".//class")
                methods = root.findall(".//method")
                print(f"  - Contains: {len(packages)} packages, {len(classes)} classes, {len(methods)} methods")
        except Exception as e:
            print(f"Error validating report {report_path}: {e}")
    
    return valid_reports

def detect_project_structure(base_dir='.', debug=False):
    """Detect the project structure to find source and test directories."""
    print("Detecting project structure...")
    
    modules = []
    
    # Find all pom.xml files (Maven projects)
    pom_files_cmd = f"find {base_dir} -name 'pom.xml' -not -path '*/target/*'"
    pom_files = subprocess.run(pom_files_cmd, shell=True, capture_output=True, text=True).stdout.strip().split('\n')
    
    for pom_file in pom_files:
        if not pom_file:
            continue
            
        try:
            with open(pom_file, 'r') as f:
                content = f.read()
                
            # Extract project name
            match = re.search(r'<artifactId>(.*?)</artifactId>', content)
            if match:
                artifact_id = match.group(1)
                
                # Determine if it's a module directory
                module_dir = os.path.dirname(pom_file)
                
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
        except Exception as e:
            print(f"Error processing POM file {pom_file}: {e}")
    
    print(f"Found {len(modules)} Maven modules")
    for module in modules:
        print(f"  - {module['name']}: {module['dir']}")
    
    return modules

def find_coverage_gaps(jacoco_path, min_coverage=80.0):
    """Find methods with low coverage from JaCoCo report."""
    print(f"Analyzing coverage report at {jacoco_path}")
    
    try:
        tree = ET.parse(jacoco_path)
        root = tree.getroot()
        coverage_gaps = []
        
        for package in root.findall(".//package"):
            package_name = package.attrib.get('name', '').replace('/', '.')
            
            # Skip generated classes
            if (package_name.startswith('ws.example.ws.xml.jakarta') or 
                'wsdlfirstservice' in package_name.lower() or 
                'mtomservice' in package_name.lower()):
                continue
            
            # Focus on our own classes
            if not package_name.startswith('org.kiwiproject'):
                continue
            
            for clazz in package.findall("class"):
                class_name = clazz.attrib.get('name', '').replace('/', '.')
                
                # Skip test classes, generated classes, etc.
                if ('Test' in class_name or 
                    'Example' in class_name or
                    class_name.endswith('Builder')):
                    continue
                
                # Check if class has methods with low coverage
                class_methods = []
                total_class_methods = 0
                covered_class_methods = 0
                
                for method in clazz.findall("method"):
                    method_name = method.attrib.get('name', '')
                    
                    # Skip constructors, getters/setters, and other utility methods
                    if (method_name == "<init>" or 
                        method_name.startswith("get") or 
                        method_name.startswith("set") or
                        method_name.startswith("is") or
                        method_name == "toString" or
                        method_name == "hashCode" or
                        method_name == "equals"):
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
                        'methods': sorted(class_methods, key=lambda x: x['priority'], reverse=True),
                        'class_coverage': class_coverage,
                        'priority': sum(m['missed_instructions'] for m in class_methods)  # Sum of all missed instructions
                    })
                    
                    print(f"Class {class_name}: coverage={class_coverage:.1f}%, methods={len(class_methods)}/{total_class_methods} need testing")
        
        # Sort by priority (descending)
        coverage_gaps.sort(key=lambda x: x['priority'], reverse=True)
        
        print(f"\nFound {len(coverage_gaps)} classes with methods needing improved coverage")
        return coverage_gaps
        
    except Exception as e:
        print(f"Error parsing JaCoCo report: {e}")
        import traceback
        traceback.print_exc()
        return []

def generate_test_template(class_name, methods):
    """Generate a template test class."""
    parts = class_name.split('.')
    package_name = '.'.join(parts[:-1])
    simple_name = parts[-1]
    
    template = f"""package {package_name};

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * Tests for {simple_name}
 */
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
        // Given
        
        // When
        
        // Then
        
    }}
"""
    
    template += "}\n"
    return template

def find_source_file(class_name, modules):
    """Find the source file for a class using the module structure."""
    # Extract package and class name
    parts = class_name.split('.')
    simple_name = parts[-1]
    package_path = '/'.join(parts[:-1])
    
    # Try direct path first in each module's source directory
    for module in modules:
        src_dir = module['src_dir']
        if not os.path.exists(src_dir):
            continue
            
        class_path = os.path.join(src_dir, package_path, f"{simple_name}.java")
        
        if os.path.exists(class_path):
            return class_path
    
    # If not found, try to find by simple name using find command
    find_cmd = f"find {' '.join([m['src_dir'] for m in modules if os.path.exists(m['src_dir'])])} -name '{simple_name}.java' 2>/dev/null"
    
    try:
        result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            files = result.stdout.strip().split('\n')
            
            # Filter by package if possible
            for file in files:
                if package_path in file:
                    return file
                    
            # If no exact match, return the first one
            return files[0]
    except Exception as e:
        print(f"Error finding source file: {e}")
    
    print(f"Could not find source file for {class_name}")
    return None

def write_test_class(class_name, test_code, modules):
    """Write the test class to a file in the appropriate module."""
    parts = class_name.split('.')
    package_name = '.'.join(parts[:-1])
    simple_name = parts[-1]
    
    # Find the right module - prefer the module that contains the source class
    target_module = None
    source_file = find_source_file(class_name, modules)
    
    if source_file:
        for module in modules:
            if source_file.startswith(os.path.abspath(module['dir'])):
                target_module = module
                break
    
    # If no specific module found, use the first one with a test directory
    if not target_module:
        for module in modules:
            if module['test_dir']:
                target_module = module
                break
    
    if not target_module:
        print(f"No suitable test directory found for {class_name}")
        return None
    
    # Create test directory
    package_path = package_name.replace('.', '/')
    test_dir = os.path.join(target_module['test_dir'], package_path)
    os.makedirs(test_dir, exist_ok=True)
    
    # Write test file
    test_file = os.path.join(test_dir, f"{simple_name}Test.java")
    with open(test_file, 'w') as f:
        f.write(test_code)
    
    print(f"Wrote test class to {test_file}")
    return test_file

def main():
    """Main function to generate tests."""
    args = parse_args()
    
    # Get absolute path to base directory
    base_dir = os.path.abspath(args.base_dir)
    
    # Find JaCoCo reports
    jacoco_reports = find_jacoco_reports(base_dir)
    
    if not jacoco_reports:
        print("No JaCoCo reports found. Cannot continue.")
        return
    
    # Use the first report found
    jacoco_report = jacoco_reports[0]
    print(f"Using JaCoCo report: {jacoco_report}")
    
    # Detect project structure
    modules = detect_project_structure(base_dir)
    
    # Find coverage gaps
    coverage_gaps = find_coverage_gaps(jacoco_report, args.min_coverage)
    if not coverage_gaps:
        print("No coverage gaps found!")
        return
    
    print(f"Found {len(coverage_gaps)} classes with low coverage")
    
    # Process classes with the most coverage gaps, up to max_classes
    processed_count = 0
    for class_data in coverage_gaps[:args.max_classes]:
        class_name = class_data['class']
        
        print(f"\nProcessing {class_name} with {len(class_data['methods'])} methods to test")
        print(f"Class coverage: {class_data['class_coverage']:.1f}%")
        
        # Generate tests
        print(f"Methods to test:")
        for method in class_data['methods']:
            print(f"  - {method['method']} (coverage: {method['coverage_percentage']:.1f}%)")
        
        # Generate a simple test template
        test_code = generate_test_template(class_name, class_data['methods'])
        
        # Write test class
        if write_test_class(class_name, test_code, modules):
            processed_count += 1
    
    print(f"\nGenerated test templates for {processed_count} classes")

if __name__ == "__main__":
    main()