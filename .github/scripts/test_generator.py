#!/usr/bin/env python3
"""
Improved Test Generator for Jakarta XML-WS Projects
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
try:
    from sambanova_api_helper import SambaNovaCoder
except ImportError:
    print("SambaNova API helper not found. Will attempt to create a basic version.")
    SambaNovaCoder = None

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
        cmd = f"find {base_dir} -path '{pattern}'"
        debug_print(f"Running command: {cmd}", debug)
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                reports = result.stdout.strip().split('\n')
                debug_print(f"Found reports: {reports}", debug)
                found_reports.extend(reports)
        except Exception as e:
            print(f"Error searching for pattern {pattern}: {e}")
    
    # Remove duplicates and check if reports are valid
    valid_reports = []
    seen_paths = set()
    
    for report_path in found_reports:
        if not report_path or report_path in seen_paths:
            continue
            
        seen_paths.add(report_path)
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
            else:
                debug_print(f"Invalid JaCoCo report structure: {report_path}", debug)
        except Exception as e:
            debug_print(f"Error validating report {report_path}: {e}", debug)
    
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
                        'test_dir': src_test_java if os.path.exists(src_test_java) else None,
                        'pom_file': pom_file
                    })
                    debug_print(f"Found Maven module: {artifact_id} at {module_dir}", debug)
        except Exception as e:
            debug_print(f"Error processing POM file {pom_file}: {e}", debug)
    
    print(f"Found {len(modules)} Maven modules")
    for module in modules:
        print(f"  - {module['name']}: {module['dir']}")
        if not module['test_dir']:
            print(f"    WARNING: No test directory found for {module['name']}")
            # Create test directory if it doesn't exist
            test_dir = os.path.join(module['dir'], "src/test/java")
            os.makedirs(test_dir, exist_ok=True)
            module['test_dir'] = test_dir
            print(f"    Created test directory: {test_dir}")
    
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
                
                # Skip test classes, generated classes, and specific patterns
                if ('Test' in class_name or 
                    'Example' in class_name or
                    '.ws.example.' in class_name or
                    class_name.endswith('Builder')):
                    debug_print(f"Skipping test/example/generated class: {class_name}", debug)
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
                    
                    # Skip constructors, getters/setters, and other patterns
                    if (method_name == "<init>" or 
                        method_name.startswith("get") or 
                        method_name.startswith("set") or
                        method_name.startswith("is") or
                        method_name == "toString" or
                        method_name == "hashCode" or
                        method_name == "equals"):
                        debug_print(f"Skipping constructor/getter/setter: {method_name}", debug)
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
                            method_data = {
                                'method': method_name,
                                'coverage_percentage': coverage,
                                'missed_instructions': missed,
                                'priority': missed  # Higher priority for more missed instructions
                            }
                            class_methods.append(method_data)
                
                # Only include classes with methods that need testing
                if class_methods:
                    # Calculate overall class coverage percentage
                    class_coverage = 0 if total_class_methods == 0 else (covered_class_methods / total_class_methods) * 100
                    
                    coverage_gaps.append({
                        'package': package_name,
                        'class': class_name,
                        'source_file': source_file_name,
                        'methods': sorted(class_methods, key=lambda x: x['priority'], reverse=True),
                        'class_coverage': class_coverage,
                        'priority': sum(m['missed_instructions'] for m in class_methods)  # Sum of all missed instructions
                    })
                    
                    print(f"Class {class_name}: coverage={class_coverage:.1f}%, methods={len(class_methods)}/{total_class_methods} need testing")
        
        # Sort by priority (descending)
        coverage_gaps.sort(key=lambda x: x['priority'], reverse=True)
        
        # Summary
        print(f"\nFound {len(coverage_gaps)} classes with methods needing improved coverage")
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
        if not os.path.exists(src_dir):
            continue
            
        class_path = os.path.join(src_dir, package_path, f"{simple_name}.java")
        debug_print(f"  Checking {class_path}", debug)
        
        if os.path.exists(class_path):
            debug_print(f"  Found at {class_path}", debug)
            return class_path
    
    # If not found, try to find by simple name using find command
    find_cmd = f"find {' '.join([m['src_dir'] for m in modules if os.path.exists(m['src_dir'])])} -name '{simple_name}.java' 2>/dev/null"
    debug_print(f"  Running command: {find_cmd}", debug)
    
    try:
        result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
        if result.stdout.strip():
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

def create_test_class_directory(package: str, module_test_dir: str) -> str:
    """Create the directory structure for a test class."""
    package_path = os.path.join(module_test_dir, package.replace('.', '/'))
    os.makedirs(package_path, exist_ok=True)
    return package_path

def find_appropriate_test_module(class_name: str, modules: List[Dict], debug: bool = False) -> Dict:
    """Find the appropriate module for writing tests for a class."""
    parts = class_name.split('.')
    package_name = '.'.join(parts[:-1])
    simple_name = parts[-1]
    
    # First try to find a module containing the source class
    source_file = find_source_file(class_name, modules, debug)
    if source_file:
        for module in modules:
            if source_file.startswith(os.path.abspath(module['dir'])):
                debug_print(f"Found source module for {class_name}: {module['name']}", debug)
                return module
    
    # If not found, try to find by package namespace
    for module in modules:
        module_classes_cmd = f"find {module['src_dir']} -name '*.java' 2>/dev/null | head -n 1"
        result = subprocess.run(module_classes_cmd, shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            first_file = result.stdout.strip()
            with open(first_file, 'r') as f:
                content = f.read()
                first_pkg_match = re.search(r'package\s+([\w.]+)', content)
                if first_pkg_match:
                    module_pkg = first_pkg_match.group(1)
                    common_prefix = os.path.commonprefix([module_pkg, package_name])
                    if len(common_prefix) > 0 and common_prefix.count('.') >= 2:
                        debug_print(f"Found module with matching package for {class_name}: {module['name']}", debug)
                        return module
    
    # If still not found, use the first module that has a test directory
    for module in modules:
        if module['test_dir']:
            debug_print(f"Using first available module with test dir for {class_name}: {module['name']}", debug)
            return module
    
    # Last resort, use the first module
    debug_print(f"Using first module for {class_name}: {modules[0]['name']}", debug)
    return modules[0]

def write_test_class(class_name: str, test_code: str, modules: List[Dict], debug: bool = False) -> str:
    """Write the test class to a file in the appropriate module."""
    parts = class_name.split('.')
    package_name = '.'.join(parts[:-1])
    simple_name = parts[-1]
    
    # Find appropriate module
    target_module = find_appropriate_test_module(class_name, modules, debug)
    
    if not target_module['test_dir']:
        print(f"No test directory found for {class_name}. Cannot write test class.")
        return None
    
    # Create test directory if needed
    test_dir = create_test_class_directory(package_name, target_module['test_dir'])
    
    # Clean up test code if needed
    if not test_code.strip().startswith('package '):
        test_code = f"package {package_name};\n\n{test_code}"
    
    # Ensure test code uses jakarta imports, not javax
    test_code = test_code.replace('javax.', 'jakarta.')
    
    # Write the test file
    test_file_path = os.path.join(test_dir, f"{simple_name}Test.java")
    with open(test_file_path, 'w') as f:
        f.write(test_code)
    
    print(f"Wrote test class to {test_file_path}")
    return test_file_path

def create_sambanova_client():
    """Create SambaNova client for test generation."""
    if SambaNovaCoder is not None:
        try:
            return SambaNovaCoder()
        except Exception as e:
            print(f"Error creating SambaNova client: {e}")
            # Try to import from local file
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                sys.path.append(script_dir)
                from sambanova_api_helper import SambaNovaCoder as LocalSambaNovaCoder
                return LocalSambaNovaCoder()
            except Exception as e2:
                print(f"Error importing local SambaNova helper: {e2}")
                return None
    
    # If we get here, we need to create a basic version of the api helper
    print("Using basic version of SambaNova API helper")
    from sambanova_api_basic import create_basic_api_helper
    return create_basic_api_helper()

def generate_tests(class_source: str, class_name: str, methods: List[Dict], client, debug: bool = False):
    """Generate test code using SambaNova API."""
    if not client:
        print("No API client available. Generating template instead.")
        return generate_test_template(class_name, methods)
    
    try:
        print(f"Generating tests for {class_name} with {len(methods)} methods...")
        test_code = client.generate_complete_test_class(class_source, class_name, methods)
        
        if test_code and len(test_code) > 100:  # Basic check for valid response
            print(f"Successfully generated test code ({len(test_code)} characters)")
            return test_code
        else:
            print("Generated test code seems invalid. Falling back to template.")
            return generate_test_template(class_name, methods)
    except Exception as e:
        print(f"Error generating tests: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return generate_test_template(class_name, methods)

def generate_test_template(class_name: str, methods: List[Dict]) -> str:
    """Generate a template test class when API is not available."""
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
    
    # Create SambaNova client
    client = create_sambanova_client()
    
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
        print("No coverage gaps found that meet the criteria!")
        return
    
    print(f"Found {len(coverage_gaps)} classes with low coverage")
    
    # Process classes with the most coverage gaps, up to max_classes
    processed_count = 0
    for class_data in coverage_gaps[:args.max_classes]:
        class_name = class_data['class']
        
        # Skip classes that already have tests or those we want to ignore
        if "Example" in class_name or "AbstractBuilder" in class_name:
            print(f"Skipping {class_name} (example or abstract class)")
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
        test_code = generate_tests(class_source, class_name, class_data['methods'], client, args.debug)
        
        # Write test class
        if test_code:
            write_test_class(class_name, test_code, modules, args.debug)
            processed_count += 1
    
    print(f"\nGenerated tests for {processed_count} classes")

if __name__ == "__main__":
    # Basic SambaNova API helper when the main module isn't available
    class sambanova_api_basic:
        @staticmethod
        def create_basic_api_helper():
            class BasicSambaNovaCoder:
                def generate_complete_test_class(self, class_source, class_name, methods):
                    return generate_test_template(class_name, methods)
            return BasicSambaNovaCoder()
    
    # Add to sys.modules so it can be imported
    sys.modules['sambanova_api_basic'] = sambanova_api_basic
    
    main()