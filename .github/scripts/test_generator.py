#!/usr/bin/env python3
"""
AI-Powered Test Generator for Jakarta XML-WS Projects

This script analyzes JaCoCo coverage reports to identify classes with low coverage
and uses SambaNova API to generate professional-quality JUnit 5 tests.
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
import subprocess
import re
import json
import datetime
import requests
from pathlib import Path

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate AI-powered JUnit 5 tests to improve code coverage')
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
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory for test summary (default: <base-dir>/test-results)')
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
        "**/target/site/jacoco-aggregate/jacoco.xml"
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
                        'test_dir': src_test_java if os.path.exists(src_test_java) else None
                    })
                    debug_print(f"Found Maven module: {artifact_id} at {module_dir}", debug)
        except Exception as e:
            debug_print(f"Error processing POM file {pom_file}: {e}", debug)
    
    print(f"Found {len(modules)} Maven modules")
    for module in modules:
        print(f"  - {module['name']}: {module['dir']}")
        
        # Create test directory if it doesn't exist
        if not module['test_dir']:
            test_dir = os.path.join(module['dir'], "src/test/java")
            os.makedirs(test_dir, exist_ok=True)
            module['test_dir'] = test_dir
            print(f"    Created test directory: {test_dir}")
    
    return modules

def find_coverage_gaps(jacoco_path, min_coverage=80.0, debug=False):
    """Find methods with low coverage from JaCoCo report."""
    print(f"Analyzing coverage report at {jacoco_path}")
    
    try:
        tree = ET.parse(jacoco_path)
        root = tree.getroot()
        coverage_gaps = []
        
        for package in root.findall(".//package"):
            package_name = package.attrib.get('name', '').replace('/', '.')
            debug_print(f"Processing package: {package_name}", debug)
            
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
                if ('Test' in class_name):
                    continue
                
                debug_print(f"Processing class: {class_name}", debug)
                
                # Check if class has methods with low coverage
                class_methods = []
                total_class_methods = 0
                covered_class_methods = 0
                source_file_name = clazz.attrib.get('sourcefilename')
                
                for method in clazz.findall("method"):
                    method_name = method.attrib.get('name', '')
                    method_desc = method.attrib.get('desc', '')
                    
                    # Skip constructors, getters/setters, and other utility methods
                    if (method_name == "<init>" or 
                        method_name.startswith("lambda$") or
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
                        
                        debug_print(f"Method {method_name}: coverage={coverage:.1f}%, missed={missed}, covered={covered}", debug)
                        
                        # Method is considered covered if it has at least one instruction covered
                        if covered > 0:
                            covered_class_methods += 1
                        
                        # Add methods with less than min_coverage
                        if coverage < min_coverage:
                            class_methods.append({
                                'method': method_name,
                                'desc': method_desc,
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

def find_source_file(class_name, modules, debug=False):
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

def get_class_source(file_path):
    """Read the source code from a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading source file: {e}")
        return None

class SambaNovaCoder:
    """Helper class for interacting with SambaNova's Qwen2.5-Coder API for test generation."""
    
    def __init__(self, api_key=None, model="Qwen2.5-Coder-32B-Instruct", debug=False):
        """Initialize with API key and model name."""
        self.api_key = api_key or os.environ.get("SAMBANOVA_API_KEY")
        if not self.api_key:
            raise ValueError("SAMBANOVA_API_KEY environment variable not set")
        
        self.base_url = "https://api.sambanova.ai/v1"
        self.model = model
        self.debug = debug
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def generate_test_class(self, class_source, class_name, methods):
        """Generate a complete test class for a Java class."""
        prompt = self._create_test_class_prompt(class_source, class_name, methods)
        debug_print(f"Using prompt:\n{prompt}", self.debug)
        response = self._call_api(prompt)
        test_code = self._extract_code_from_response(response)
        return test_code
    
    def _call_api(self, prompt):
        """Make a call to the SambaNova API."""
        data = {
            "stream": False,
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": """You are a Java testing expert specializing in creating effective JUnit 5 tests for Dropwizard and Jakarta XML Web Services applications.

IMPORTANT JAKARTA XML REQUIREMENTS:
1. Always use 'jakarta.*' packages instead of 'javax.*' packages
   - Use 'jakarta.xml.ws' NOT 'javax.xml.ws'
   - Use 'jakarta.servlet' NOT 'javax.servlet'
   - Use 'jakarta.validation' NOT 'javax.validation'

2. The project uses:
   - Dropwizard 4.x
   - JUnit Jupiter (JUnit 5)
   - Mockito for mocking
   - AssertJ for assertions (import static org.assertj.core.api.Assertions.*)

3. Test structure:
   - Use @ExtendWith(MockitoExtension.class)
   - Use @Mock for dependencies
   - Use @BeforeEach for setup
   - Structure tests with Given/When/Then comments
   - Create descriptive method names (should_X_when_Y pattern)
   - Test both happy paths and edge cases

Generate complete, professional tests that thoroughly validate the functionality while following best practices."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "top_p": 0.1
        }
        
        try:
            debug_print(f"Calling SambaNova API with model: {self.model}", self.debug)
            response = requests.post(
                f"{self.base_url}/chat/completions", 
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"]
            else:
                raise ValueError(f"Unexpected response format: {result}")
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def _create_test_class_prompt(self, class_source, class_name, methods):
        """Create a prompt for generating a complete test class."""
        methods_str = "\n".join([f"- {m['method']} (current coverage: {m['coverage_percentage']:.1f}%)" for m in methods])
        parts = class_name.split('.')
        package_name = '.'.join(parts[:-1])
        simple_name = parts[-1]
        
        return f"""Generate a complete, professional JUnit 5 test class for testing {class_name}. Here's the source code:

```java
{class_source}
```

Focus on testing these methods with low coverage:
{methods_str}

Requirements:
1. The test class should be in package: {package_name}
2. The test class name should be: {simple_name}Test
3. Use proper imports (jakarta.* not javax.*)
4. Use @ExtendWith(MockitoExtension.class) for JUnit 5 
5. Use @Mock for dependencies and proper setup in @BeforeEach
6. Create descriptive test methods (should_X_when_Y pattern)
7. Include both happy path and error/edge case tests for each method
8. Use AssertJ assertions (assertThat().isEqualTo() style)
9. Structure with Given/When/Then comments
10. Be thorough and professional
11. Handle any Jakarta XML Web Services specifics appropriately

Return the COMPLETE test class including package declaration and all imports.
"""
    
    def _extract_code_from_response(self, response):
        """Extract code blocks from the API response."""
        import re
        
        # Try to find Java code blocks
        java_blocks = re.findall(r'```java\n([\s\S]*?)\n```', response)
        if java_blocks:
            return java_blocks[0]
        
        # If no code blocks with "java" tag, try without language specification
        code_blocks = re.findall(r'```\n([\s\S]*?)\n```', response)
        if code_blocks:
            return code_blocks[0]
        
        # If still no code blocks, return the whole response
        return response

def generate_fallback_test(class_name, methods):
    """Generate a fallback test class if AI generation fails."""
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
 * 
 * This is a fallback template - AI generation was not successful.
 */
@ExtendWith(MockitoExtension.class)
class {simple_name}Test {{

    private {simple_name} classUnderTest;
    
    @BeforeEach
    void setUp() {{
        classUnderTest = new {simple_name}();
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

def write_test_class(class_name, test_code, modules, debug=False):
    """Write the test class to a file in the appropriate module."""
    parts = class_name.split('.')
    package_name = '.'.join(parts[:-1])
    simple_name = parts[-1]
    
    # Find the right module - prefer the module that contains the source class
    target_module = None
    source_file = find_source_file(class_name, modules, debug)
    
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
    
    print(f"✅ Wrote AI-generated test class to {os.path.abspath(test_file)}")
    return os.path.abspath(test_file)

def create_html_report(generated_tests, output_dir):
    """Create an HTML report of the generated tests."""
    if not output_dir:
        return None
        
    os.makedirs(output_dir, exist_ok=True)
    
    report_path = os.path.join(output_dir, "test-generation-report.html")
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Test Generation Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .summary {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .file-path {{
            font-family: monospace;
            word-break: break-all;
        }}
        .methods-list {{
            font-family: monospace;
            color: #2c3e50;
        }}
    </style>
</head>
<body>
    <h1>AI-Powered Test Generation Report</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Generated {len(generated_tests)} test classes at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <h2>Generated Test Files</h2>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Class</th>
                <th>Test File Location</th>
                <th>Methods Tested</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for i, test in enumerate(generated_tests, 1):
        html += f"""
            <tr>
                <td>{i}</td>
                <td>{test['class']}</td>
                <td class="file-path">{test['test_path']}</td>
                <td class="methods-list">{', '.join(test['methods'])}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
</body>
</html>
"""
    
    with open(report_path, 'w') as f:
        f.write(html)
        
    print(f"📊 Created HTML report at {os.path.abspath(report_path)}")
    return os.path.abspath(report_path)

def main():
    """Main function to generate tests."""
    args = parse_args()
    
    # Get absolute path to base directory
    base_dir = os.path.abspath(args.base_dir)
    
    # Initialize SambaNova API client
    try:
        sambanova_client = SambaNovaCoder(debug=args.debug)
        print("✅ Connected to SambaNova API for AI-powered test generation")
    except Exception as e:
        print(f"⚠️ Could not initialize SambaNova API client: {e}")
        print("⚠️ Will use fallback test templates")
        sambanova_client = None
    
    # Find JaCoCo reports
    jacoco_reports = find_jacoco_reports(base_dir, args.debug)
    
    if not jacoco_reports:
        print("❌ No JaCoCo reports found. Cannot continue.")
        return
    
    # Use the first report found
    jacoco_report = jacoco_reports[0]
    print(f"Using JaCoCo report: {jacoco_report}")
    
    # Detect project structure
    modules = detect_project_structure(base_dir, args.debug)
    
    # Find coverage gaps
    coverage_gaps = find_coverage_gaps(jacoco_report, args.min_coverage, args.debug)
    if not coverage_gaps:
        print("✅ No coverage gaps found!")
        return
    
    print(f"Found {len(coverage_gaps)} classes with low coverage")
    
    # Process classes with the most coverage gaps, up to max_classes
    processed_count = 0
    generated_tests = []
    
    for class_data in coverage_gaps[:args.max_classes]:
        class_name = class_data['class']
        
        print(f"\nProcessing {class_name} with {len(class_data['methods'])} methods to test")
        print(f"Class coverage: {class_data['class_coverage']:.1f}%")
        
        # Get source file
        source_file = find_source_file(class_name, modules, args.debug)
        if not source_file:
            print(f"❌ Could not find source file for {class_name}, skipping")
            continue
            
        class_source = get_class_source(source_file)
        if not class_source:
            print(f"❌ Could not read source for {class_name}, skipping")
            continue
        
        # Generate tests
        print(f"Methods to test:")
        method_names = []
        for method in class_data['methods']:
            method_names.append(method['method'])
            print(f"  - {method['method']} (coverage: {method['coverage_percentage']:.1f}%)")
        
        # Generate test code - try AI first, fallback to template
        test_code = None
        if sambanova_client:
            try:
                print(f"🤖 Generating AI-powered tests with SambaNova for {class_name}...")
                test_code = sambanova_client.generate_test_class(class_source, class_name, class_data['methods'])
                print(f"✅ Successfully generated AI-powered tests for {class_name}")
            except Exception as e:
                print(f"⚠️ AI test generation failed: {e}")
                print(f"⚠️ Using fallback template for {class_name}")
        
        if not test_code:
            test_code = generate_fallback_test(class_name, class_data['methods'])
        
        # Fix common issues with generated tests
        test_code = test_code.replace('javax.', 'jakarta.')
        
        # Write test class
        test_path = write_test_class(class_name, test_code, modules, args.debug)
        if test_path:
            processed_count += 1
            generated_tests.append({
                'class': class_name,
                'test_path': test_path,
                'methods': method_names
            })
    
    print(f"\n🎉 Generated AI-powered test classes for {processed_count} classes")
    
    # Print table of generated files
    if generated_tests:
        print("\n=== Generated Test Files ===")
        print("%-4s %-50s %s" % ("#", "Class", "Location"))
        print("-" * 100)
        
        for i, test in enumerate(generated_tests, 1):
            print("%-4d %-50s %s" % (i, test['class'], test['test_path']))
            
    # Create HTML report if output directory is specified
    if args.output_dir:
        report_path = create_html_report(generated_tests, args.output_dir)
        if report_path:
            print(f"\n📊 HTML report available at: {report_path}")

if __name__ == "__main__":
    main()