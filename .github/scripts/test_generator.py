#!/usr/bin/env python3
"""
Professional Test Generator for Jakarta XML-WS Projects

This script analyzes JaCoCo coverage reports to identify classes with low coverage
and generates professional-quality JUnit 5 tests for them.
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
import subprocess
import re
import inspect
from pathlib import Path

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate professional JUnit 5 tests to improve code coverage')
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

def find_jacoco_reports(base_dir='.'):
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

def detect_project_structure(base_dir='.'):
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
        
        # Create test directory if it doesn't exist
        if not module['test_dir']:
            test_dir = os.path.join(module['dir'], "src/test/java")
            os.makedirs(test_dir, exist_ok=True)
            module['test_dir'] = test_dir
            print(f"    Created test directory: {test_dir}")
    
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
                if ('Test' in class_name):
                    continue
                
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

def analyze_source_file(file_path):
    """Extract information from the source file to help with test generation."""
    if not file_path or not os.path.exists(file_path):
        return None
        
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        class_info = {
            'imports': [],
            'fields': [],
            'constructor_params': [],
            'annotations': [],
            'interfaces': [],
            'is_abstract': False
        }
        
        # Extract imports
        imports = re.findall(r'^import\s+(.*?);', content, re.MULTILINE)
        class_info['imports'] = imports
        
        # Check if class is abstract
        class_match = re.search(r'(public\s+)?abstract\s+class', content)
        if class_match:
            class_info['is_abstract'] = True
            
        # Extract interfaces
        implements_match = re.search(r'implements\s+(.*?)(?:\{|extends)', content)
        if implements_match:
            interfaces = implements_match.group(1).strip().split(',')
            class_info['interfaces'] = [i.strip() for i in interfaces]
            
        # Extract field declarations to determine dependencies
        field_matches = re.findall(r'^\s*(private|protected)\s+(\w+(?:<.*?>)?)\s+(\w+)(?:\s*=\s*.*?)?;', content, re.MULTILINE)
        for field_match in field_matches:
            _, field_type, field_name = field_match
            if not field_type.startswith('final') and not field_type in ['String', 'int', 'long', 'boolean', 'double', 'float']:
                class_info['fields'].append({
                    'name': field_name,
                    'type': field_type
                })
                
        # Extract constructor parameters
        constructor_match = re.search(r'public\s+\w+\s*\((.*?)\)', content)
        if constructor_match:
            params_str = constructor_match.group(1)
            if params_str.strip():
                params = params_str.split(',')
                for param in params:
                    param = param.strip()
                    if param:
                        param_parts = param.split()
                        if len(param_parts) >= 2:
                            class_info['constructor_params'].append({
                                'type': param_parts[0],
                                'name': param_parts[1]
                            })
        
        # Extract class-level annotations
        annotation_matches = re.findall(r'^\s*@(\w+)(?:\(.*?\))?', content, re.MULTILINE)
        class_info['annotations'] = annotation_matches
        
        return class_info
    except Exception as e:
        print(f"Error analyzing source file {file_path}: {e}")
        return None

def generate_professional_test(class_name, methods, source_info=None):
    """Generate a professional JUnit 5 test class."""
    parts = class_name.split('.')
    package_name = '.'.join(parts[:-1])
    simple_name = parts[-1]
    
    # Determine dependencies to mock based on source analysis
    mocks = []
    setup_code = []
    
    if source_info:
        for field in source_info.get('fields', []):
            if 'DAO' in field['type'] or 'Repository' in field['type'] or 'Service' in field['type']:
                mocks.append(field)
                
        # Handle interfaces
        implements_web_service = any('Service' in intf for intf in source_info.get('interfaces', []))
        
    # Imports
    imports = [
        f"package {package_name};",
        "",
        "import static org.assertj.core.api.Assertions.assertThat;",
        "import static org.assertj.core.api.Assertions.assertThatThrownBy;",
        "import static org.mockito.Mockito.*;",
        "",
        "import org.junit.jupiter.api.BeforeEach;",
        "import org.junit.jupiter.api.Test;",
        "import org.junit.jupiter.api.extension.ExtendWith;",
        "import org.mockito.Mock;",
        "import org.mockito.junit.jupiter.MockitoExtension;",
        "import org.mockito.ArgumentCaptor;"
    ]
    
    # Add Jakarta-specific imports if needed
    if 'xml.ws' in class_name:
        imports.extend([
            "import jakarta.xml.ws.WebServiceContext;",
            "import jakarta.xml.ws.handler.MessageContext;"
        ])
        
    # Add DAO imports
    if 'DAO' in simple_name or 'Repository' in simple_name:
        imports.extend([
            "import java.util.List;",
            "import java.util.Optional;",
            "import org.hibernate.Session;",
            "import org.hibernate.SessionFactory;",
            "import org.hibernate.Transaction;"
        ])
        
    imports.append("")
    
    # Class declaration
    test_class = f"""/**
 * Professional JUnit 5 tests for {simple_name}
 * 
 * Tests focus on both happy path and edge cases.
 */
@ExtendWith(MockitoExtension.class)
class {simple_name}Test {{
"""
    
    # Mocks section
    if 'xml.ws' in class_name:
        mocks.append({'name': 'wsContext', 'type': 'WebServiceContext'})
        
    if 'DAO' in simple_name or 'Repository' in simple_name:
        mocks.append({'name': 'sessionFactory', 'type': 'SessionFactory'})
        mocks.append({'name': 'session', 'type': 'Session'})
        mocks.append({'name': 'transaction', 'type': 'Transaction'})
        
    for mock in mocks:
        test_class += f"    @Mock\n    private {mock['type']} {mock['name']};\n"
        
    test_class += "\n"
    
    # Class under test
    test_class += f"    private {simple_name} classUnderTest;\n\n"
    
    # Setup method
    test_class += "    @BeforeEach\n    void setUp() {\n"
    
    setup_args = []
    
    # For DAO classes
    if 'DAO' in simple_name or 'Repository' in simple_name:
        setup_code.extend([
            "when(sessionFactory.openSession()).thenReturn(session);",
            "when(session.getTransaction()).thenReturn(transaction);"
        ])
        setup_args.append("sessionFactory")
        
    # For web service implementations
    elif 'xml.ws' in class_name:
        setup_code.append("when(wsContext.getMessageContext()).thenReturn(mock(MessageContext.class));")
        
    # Add setup code
    for code in setup_code:
        test_class += f"        {code}\n"
        
    # Initialize class under test
    if setup_args:
        test_class += f"        classUnderTest = new {simple_name}({', '.join(setup_args)});\n"
    else:
        test_class += f"        classUnderTest = new {simple_name}();\n"
        
    test_class += "    }\n\n"
    
    # Test methods
    for method in methods:
        method_name = method['method']
        
        # Generate professional test methods based on method type
        
        # DAO methods
        if 'DAO' in simple_name or 'Repository' in simple_name:
            if method_name == 'findById':
                test_class += generate_dao_findbyid_test(simple_name, method)
            elif method_name == 'findAll':
                test_class += generate_dao_findall_test(simple_name, method)
            elif method_name == 'create' or method_name == 'save':
                test_class += generate_dao_create_test(simple_name, method)
            else:
                test_class += generate_generic_test(simple_name, method)
                
        # Web service methods
        elif 'xml.ws' in class_name:
            if method_name == 'echo':
                test_class += generate_echo_test(simple_name, method)
            elif 'Async' in method_name:
                test_class += generate_async_test(simple_name, method)
            else:
                test_class += generate_web_service_test(simple_name, method)
                
        # Authentication methods
        elif 'Authenticator' in simple_name:
            test_class += generate_authenticator_test(simple_name, method)
            
        # Generic methods
        else:
            test_class += generate_generic_test(simple_name, method)
    
    # Close class
    test_class += "}\n"
    
    # Combine imports and class
    full_test = "\n".join(imports) + "\n\n" + test_class
    
    return full_test

def generate_dao_findbyid_test(class_name, method):
    """Generate tests for DAO findById method."""
    return f"""    @Test
    void should_find_by_id_when_record_exists() {{
        // Given
        Long id = 1L;
        var expectedEntity = mock(Object.class);
        when(session.get(any(), eq(id))).thenReturn(expectedEntity);
        
        // When
        var result = classUnderTest.findById(id);
        
        // Then
        assertThat(result).isPresent();
        assertThat(result.get()).isSameAs(expectedEntity);
        verify(session).get(any(), eq(id));
    }}
    
    @Test
    void should_return_empty_optional_when_record_not_found() {{
        // Given
        Long id = 999L;
        when(session.get(any(), eq(id))).thenReturn(null);
        
        // When
        var result = classUnderTest.findById(id);
        
        // Then
        assertThat(result).isEmpty();
        verify(session).get(any(), eq(id));
    }}

"""

def generate_dao_findall_test(class_name, method):
    """Generate tests for DAO findAll method."""
    return f"""    @Test
    void should_find_all_records() {{
        // Given
        var mockQuery = mock(org.hibernate.query.Query.class);
        var expectedResults = List.of(mock(Object.class), mock(Object.class));
        
        when(session.createNamedQuery(anyString())).thenReturn(mockQuery);
        when(mockQuery.list()).thenReturn(expectedResults);
        
        // When
        var result = classUnderTest.findAll();
        
        // Then
        assertThat(result).hasSize(2);
        assertThat(result).isSameAs(expectedResults);
        verify(session).createNamedQuery(anyString());
        verify(mockQuery).list();
    }}
    
    @Test
    void should_return_empty_list_when_no_records_exist() {{
        // Given
        var mockQuery = mock(org.hibernate.query.Query.class);
        var emptyList = List.of();
        
        when(session.createNamedQuery(anyString())).thenReturn(mockQuery);
        when(mockQuery.list()).thenReturn(emptyList);
        
        // When
        var result = classUnderTest.findAll();
        
        // Then
        assertThat(result).isEmpty();
        verify(session).createNamedQuery(anyString());
        verify(mockQuery).list();
    }}

"""

def generate_dao_create_test(class_name, method):
    """Generate tests for DAO create/save method."""
    return f"""    @Test
    void should_create_entity_successfully() {{
        // Given
        var entity = mock(Object.class);
        when(session.persist(any())).thenReturn(entity);
        
        // When
        var result = classUnderTest.create(entity);
        
        // Then
        assertThat(result).isSameAs(entity);
        verify(session).persist(entity);
        verify(transaction, never()).rollback();
    }}
    
    @Test
    void should_handle_exception_during_create() {{
        // Given
        var entity = mock(Object.class);
        when(session.persist(any())).thenThrow(new RuntimeException("Database error"));
        
        // When/Then
        assertThatThrownBy(() -> classUnderTest.create(entity))
            .isInstanceOf(RuntimeException.class)
            .hasMessageContaining("Database error");
            
        verify(session).persist(entity);
    }}

"""

def generate_echo_test(class_name, method):
    """Generate tests for echo method in web services."""
    return f"""    @Test
    void should_echo_valid_input() {{
        // Given
        String input = "Hello, World!";
        
        // When
        var result = classUnderTest.echo(input);
        
        // Then
        assertThat(result).contains(input);
    }}
    
    @Test
    void should_reject_invalid_input() {{
        // Given
        String input = null;
        
        // When/Then
        assertThatThrownBy(() -> classUnderTest.echo(input))
            .isInstanceOf(Exception.class);
    }}
    
    @Test
    void should_reject_empty_input() {{
        // Given
        String input = "";
        
        // When/Then
        assertThatThrownBy(() -> classUnderTest.echo(input))
            .isInstanceOf(Exception.class);
    }}

"""

def generate_async_test(class_name, method):
    """Generate tests for async methods in web services."""
    return f"""    @Test
    void should_process_{method['method']}_asynchronously() {{
        // Given
        var input = mock(Object.class);
        var asyncHandler = mock(jakarta.xml.ws.AsyncHandler.class);
        
        // When
        var future = classUnderTest.{method['method']}(input, asyncHandler);
        
        // Then
        assertThat(future).isNotNull();
        // Note: Complete testing would require waiting for the async operation
        // This is a basic structural test
    }}

"""

def generate_web_service_test(class_name, method):
    """Generate tests for web service methods."""
    return f"""    @Test
    void should_process_{method['method']}_successfully() {{
        // Given
        var input = mock(Object.class);
        
        // When
        var result = classUnderTest.{method['method']}(input);
        
        // Then
        assertThat(result).isNotNull();
    }}
    
    @Test
    void should_handle_errors_in_{method['method']}() {{
        // Given
        var input = null;
        
        // When/Then
        assertThatThrownBy(() -> classUnderTest.{method['method']}(input))
            .isInstanceOf(Exception.class);
    }}

"""

def generate_authenticator_test(class_name, method):
    """Generate tests for authenticator methods."""
    return f"""    @Test
    void should_authenticate_with_valid_credentials() {{
        // Given
        var credentials = new io.dropwizard.auth.basic.BasicCredentials("username", "secret");
        
        // When
        var result = classUnderTest.authenticate(credentials);
        
        // Then
        assertThat(result).isPresent();
        assertThat(result.get().getName()).isEqualTo("username");
    }}
    
    @Test
    void should_reject_invalid_credentials() {{
        // Given
        var credentials = new io.dropwizard.auth.basic.BasicCredentials("username", "wrong-password");
        
        // When
        var result = classUnderTest.authenticate(credentials);
        
        // Then
        assertThat(result).isEmpty();
    }}
    
    @Test
    void should_handle_null_credentials() {{
        // Given
        var credentials = null;
        
        // When/Then
        assertThatThrownBy(() -> classUnderTest.authenticate(credentials))
            .isInstanceOf(NullPointerException.class);
    }}

"""

def generate_generic_test(class_name, method):
    """Generate tests for generic methods."""
    return f"""    @Test
    void should_{method['method']}_successfully() {{
        // Given
        // TODO: Set up test inputs and mocks
        
        // When
        // TODO: Call the method
        
        // Then
        // TODO: Assert expected outcomes
    }}
    
    @Test
    void should_handle_edge_cases_in_{method['method']}() {{
        // Given
        // TODO: Set up edge case inputs
        
        // When
        // TODO: Call the method with edge case inputs
        
        // Then
        // TODO: Assert expected behavior for edge cases
    }}

"""

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
    
    print(f"✅ Wrote professional test class to {os.path.abspath(test_file)}")
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
    <title>Test Generation Report</title>
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
    <h1>Professional Test Generation Report</h1>
    
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
    
    # Find JaCoCo reports
    jacoco_reports = find_jacoco_reports(base_dir)
    
    if not jacoco_reports:
        print("❌ No JaCoCo reports found. Cannot continue.")
        return
    
    # Use the first report found
    jacoco_report = jacoco_reports[0]
    print(f"Using JaCoCo report: {jacoco_report}")
    
    # Detect project structure
    modules = detect_project_structure(base_dir)
    
    # Find coverage gaps
    coverage_gaps = find_coverage_gaps(jacoco_report, args.min_coverage)
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
        
        # Get source file for analysis
        source_file = find_source_file(class_name, modules)
        source_info = None
        
        if source_file:
            source_info = analyze_source_file(source_file)
        
        # Generate tests
        print(f"Methods to test:")
        method_names = []
        for method in class_data['methods']:
            method_names.append(method['method'])
            print(f"  - {method['method']} (coverage: {method['coverage_percentage']:.1f}%)")
        
        # Generate professional test code
        test_code = generate_professional_test(class_name, class_data['methods'], source_info)
        
        # Write test class
        test_path = write_test_class(class_name, test_code, modules)
        if test_path:
            processed_count += 1
            generated_tests.append({
                'class': class_name,
                'test_path': test_path,
                'methods': method_names
            })
    
    print(f"\n📝 Generated professional test classes for {processed_count} classes")
    
    # Print table of generated files
    if generated_tests:
        print("\n=== Generated Test Files ===")
        print("%-4s %-50s %s" % ("#", "Class", "Location"))
        print("-" * 100)
        
        for i, test in enumerate(generated_tests, 1):
            print("%-4d %-50s %s" % (i, test['class'], test['test_path']))
            
    # Create HTML report if output directory is specified
    if args.output_dir:
        import datetime
        report_path = create_html_report(generated_tests, args.output_dir)
        if report_path:
            print(f"\n📊 HTML report available at: {report_path}")

if __name__ == "__main__":
    main()