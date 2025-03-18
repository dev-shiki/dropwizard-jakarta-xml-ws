#!/usr/bin/env python3
"""
Test Generator using SonarQube API
"""

import os
import sys
import argparse
import requests
from typing import List, Dict, Any
import subprocess

# Import SambaNova helper (assume it's already defined)
from sambanova_api_helper import SambaNovaCoder

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate tests using SonarQube coverage data')
    parser.add_argument('--max-classes', type=int, default=5,
                        help='Maximum number of classes to generate tests for')
    parser.add_argument('--src-dir', type=str, default='src/main/java',
                        help='Source directory for Java classes')
    parser.add_argument('--test-dir', type=str, default='src/test/java',
                        help='Directory to write generated tests to')
    parser.add_argument('--project-key', type=str, default='dev-shiki_dropwizard-jakarta-xml-ws',
                        help='SonarQube project key')
    return parser.parse_args()

class SonarQubeClient:
    """Client for SonarQube API."""
    
    def __init__(self, token=None, url="https://sonarcloud.io", project_key=None):
        """Initialize with API token and URL."""
        self.token = token or os.environ.get("SONAR_TOKEN")
        if not self.token:
            raise ValueError("SONAR_TOKEN environment variable not set")
        
        self.url = url
        self.project_key = project_key
        self.auth = (self.token, '')
    
    def get_coverage_data(self) -> List[Dict[str, Any]]:
        """Get coverage data from SonarQube."""
        # Get components with poor coverage
        components_url = f"{self.url}/api/measures/component_tree"
        params = {
            "component": self.project_key,
            "metricKeys": "coverage,uncovered_lines",
            "strategy": "leaves",
            "qualifiers": "FIL"  # Only files
        }
        
        try:
            response = requests.get(components_url, auth=self.auth, params=params)
            response.raise_for_status()
            components_data = response.json()
            
            # Filter components with coverage < 80%
            low_coverage_components = []
            for component in components_data.get("components", []):
                # Skip test files
                if "Test" in component.get("name", ""):
                    continue
                
                measures = {m["metric"]: m["value"] for m in component.get("measures", [])}
                coverage = float(measures.get("coverage", "100"))
                uncovered_lines = int(measures.get("uncovered_lines", "0"))
                
                if coverage < 80 and uncovered_lines > 0:
                    # Get component name and path
                    name = component.get("name", "").replace(".java", "")
                    path = component.get("path", "")
                    
                    # Extract methods with poor coverage
                    methods = self._get_methods_with_poor_coverage(component.get("key"))
                    
                    if methods:
                        low_coverage_components.append({
                            "class": self._path_to_class_name(path),
                            "path": path,
                            "coverage": coverage,
                            "uncovered_lines": uncovered_lines,
                            "methods": methods,
                            "priority": uncovered_lines  # Higher priority for more uncovered lines
                        })
            
            # Sort by priority (higher first)
            low_coverage_components.sort(key=lambda x: x["priority"], reverse=True)
            return low_coverage_components
            
        except requests.RequestException as e:
            print(f"Error calling SonarQube API: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            return []
    
    def _get_methods_with_poor_coverage(self, component_key: str) -> List[Dict[str, Any]]:
        """Get methods with poor coverage for a specific component."""
        methods_url = f"{self.url}/api/coverage/list"
        params = {
            "component": component_key
        }
        
        try:
            response = requests.get(methods_url, auth=self.auth, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Extract methods with uncovered lines
            methods = []
            for coverage_item in data.get("files", []):
                for line in coverage_item.get("coveredLines", []):
                    if not line.get("covered", True):
                        line_num = line.get("line")
                        method = self._get_method_at_line(component_key, line_num)
                        if method and method not in [m["method"] for m in methods]:
                            methods.append({
                                "method": method,
                                "coverage_percentage": 0,  # We don't have exact method coverage
                                "uncovered_lines": 1  # Incremental count
                            })
            
            return methods
            
        except requests.RequestException as e:
            print(f"Error getting method coverage: {e}")
            return []
    
    def _get_method_at_line(self, component_key: str, line_num: int) -> str:
        """Get the method name for a specific line number (using source API)."""
        source_url = f"{self.url}/api/sources/show"
        params = {
            "key": component_key,
            "from": max(1, line_num - 10),
            "to": line_num + 10
        }
        
        try:
            response = requests.get(source_url, auth=self.auth, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Simplistic method detection - in a real implementation
            # this would need to be more sophisticated
            lines = data.get("sources", [])
            for line in lines:
                if line.get("line") <= line_num:
                    code = line.get("code", "")
                    if "public" in code and "(" in code and ")" in code and "{" in code:
                        # Extract method name
                        parts = code.split("(")[0].split()
                        for i, part in enumerate(parts):
                            if i > 0 and part not in ["public", "private", "protected", 
                                                    "static", "final", "synchronized", 
                                                    "void", "int", "String", "boolean"]:
                                return part
            
            return None
            
        except requests.RequestException as e:
            print(f"Error getting source code: {e}")
            return None
    
    def _path_to_class_name(self, path: str) -> str:
        """Convert a file path to a Java class name."""
        # Remove src/main/java/ prefix and .java suffix
        if path.startswith("src/main/java/"):
            path = path[len("src/main/java/"):]
        
        if path.endswith(".java"):
            path = path[:-5]
        
        # Convert slashes to dots
        return path.replace("/", ".")

def get_class_source(class_name: str, src_dir: str) -> str:
    """Get source code for a class."""
    try:
        # Split class name into package and simple name
        parts = class_name.split('.')
        simple_name = parts[-1]
        package_path = '/'.join(parts[:-1])
        
        # Try direct path first
        class_path = os.path.join(src_dir, package_path, f"{simple_name}.java")
        if os.path.exists(class_path):
            with open(class_path, 'r') as f:
                return f.read()
        
        # Try to find by just the simple name as fallback
        result = subprocess.run(['find', src_dir, '-name', f"{simple_name}.java"], 
                               capture_output=True, text=True)
        if result.stdout:
            filepath = result.stdout.strip().split('\n')[0]
            with open(filepath, 'r') as f:
                return f.read()
        
        print(f"Could not find source file for {class_name}")
        return None
    except Exception as e:
        print(f"Error reading source for {class_name}: {e}")
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
    
    # Initialize SonarQube client
    sonar_client = SonarQubeClient(project_key=args.project_key)
    
    # Get coverage data
    coverage_data = sonar_client.get_coverage_data()
    
    if not coverage_data:
        print("No coverage gaps found in SonarQube!")
        return
    
    print(f"Found {len(coverage_data)} classes with low coverage")
    
    # Initialize the SambaNova API helper
    sambanova = SambaNovaCoder()
    
    # Process classes with the most coverage gaps, up to max_classes
    processed_count = 0
    for class_data in coverage_data[:args.max_classes]:
        class_name = class_data["class"]
        
        # Skip classes that already have tests
        simple_class_name = class_name.split('.')[-1]
        package_name = '.'.join(class_name.split('.')[:-1])
        if check_test_exists(class_name, args.test_dir):
            print(f"Skipping {class_name} as it already has tests")
            continue
        
        print(f"\nProcessing {class_name} with {len(class_data['methods'])} methods")
        
        # Get class source
        class_source = get_class_source(class_name, args.src_dir)
        if not class_source:
            print(f"Could not get source for {class_name}, skipping")
            continue
        
        # Generate tests
        print(f"Generating tests for {class_name}...")
        try:
            test_code = sambanova.generate_complete_test_class(
                class_source, class_name, class_data["methods"]
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