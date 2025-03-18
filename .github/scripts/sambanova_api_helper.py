import os
import json
import requests
from typing import Dict, List, Any


class SambaNovaCoder:
    """Helper class for interacting with SambaNova's Qwen2.5-Coder API for Jakarta XML-WS test generation."""
    
    def __init__(self, api_key=None, model="Qwen2.5-Coder-32B-Instruct"):
        """Initialize with API key and model name."""
        self.api_key = api_key or os.environ.get("SAMBANOVA_API_KEY")
        if not self.api_key:
            raise ValueError("SAMBANOVA_API_KEY environment variable not set")
        
        self.base_url = "https://api.sambanova.ai/v1"
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def generate_test(self, class_source: str, class_name: str, method_name: str) -> str:
        """Generate a test for a specific method in a class."""
        prompt = self._create_test_generation_prompt(class_source, class_name, method_name)
        response = self._call_api(prompt)
        return self._extract_code_from_response(response)
    
    def generate_complete_test_class(self, class_source: str, class_name: str, methods: List[Dict[str, Any]]) -> str:
        """Generate a complete test class for a Java class."""
        prompt = self._create_test_class_prompt(class_source, class_name, methods)
        response = self._call_api(prompt)
        return self._extract_code_from_response(response)
    
    def _call_api(self, prompt: str) -> str:
        """Make a call to the SambaNova API."""
        data = {
            "stream": False,
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": """You are a Java testing expert specializing in creating effective JUnit 5 tests for Dropwizard and Jakarta XML Web Services applications.

IMPORTANT JAKARTA XML REQUIREMENTS:
1. Always use 'jakarta.*' packages instead of 'javax.*' packages, as this is a Jakarta EE application.
   - Use 'jakarta.xml.ws' NOT 'javax.xml.ws'
   - Use 'jakarta.servlet' NOT 'javax.servlet'
   - Use 'jakarta.validation' NOT 'javax.validation'
   - All other 'javax.*' imports should be 'jakarta.*'

2. The project is built on:
   - Dropwizard 4.x
   - JUnit 5 (jupiter)
   - Mockito 5.x
   - AssertJ for assertions
   - Apache CXF for SOAP services implementation

3. Common test patterns:
   - Use @ExtendWith(MockitoExtension.class) for JUnit 5 tests
   - Use @Mock for mock dependencies
   - Use @BeforeEach for setup
   - Use AssertJ for assertions (assertThat(...).isEqualTo(...))
   - Use given/when/then comments for test structure
   - Ensure all dependencies are properly mocked
   - Ensure validations are tested

The generated tests must compile without errors."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "top_p": 0.1
        }
        
        try:
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
    
    def _create_test_generation_prompt(self, class_source: str, class_name: str, method_name: str) -> str:
        """Create a prompt for generating a test for a specific method."""
        return f"""
I need you to create a JUnit 5 test for the following method in {class_name}:

```java
{class_source}
```

Focus on testing the method: {method_name}

Generate a comprehensive test that:
1. Tests the happy path
2. Tests edge cases and exceptions
3. Uses Mockito to mock dependencies
4. Uses AssertJ assertions
5. Will increase code coverage

Remember to use jakarta.* packages instead of javax.*.

Return ONLY the test method code in a Java code block.
"""
    
    def _create_test_class_prompt(self, class_source: str, class_name: str, methods: List[Dict[str, Any]]) -> str:
        """Create a prompt for generating a complete test class."""
        methods_str = "\n".join([f"- {m['method']} (current coverage: {m['coverage_percentage']:.1f}%)" for m in methods])
        package_name = '.'.join(class_name.split('.')[:-1])
        simple_class_name = class_name.split('.')[-1]
        
        return f"""
I need you to create a complete JUnit 5 test class for testing {class_name}. Here's the source code:

```java
{class_source}
```

Focus on testing these methods with low coverage:
{methods_str}

The test class should be created in the package: {package_name}
The test class name should be: {simple_class_name}Test

Requirements:
1. Include all necessary imports (using jakarta.* packages, not javax.*)
2. Include @BeforeEach method to set up test fixtures and mocks
3. Create separate test methods for each scenario
4. Use descriptive method names (should_X_when_Y pattern)
5. Mock all external dependencies
6. Test both happy paths and edge cases/exceptions
7. Ensure thorough test coverage

The tests must be compatible with:
- Dropwizard 4.x
- Jakarta XML Web Services
- JUnit Jupiter
- Mockito
- AssertJ assertions

Return the COMPLETE test class including package declaration and imports.
"""
    
    def _extract_code_from_response(self, response: str) -> str:
        """Extract code blocks from the API response."""
        import re
        
        # Try to find Java code blocks
        java_blocks = re.findall(r'```java\n([\s\S]*?)\n```', response)
        if java_blocks:
            return "\n".join(java_blocks)
        
        # If no code blocks with "java" tag, try without language specification
        code_blocks = re.findall(r'```\n([\s\S]*?)\n```', response)
        if code_blocks:
            return "\n".join(code_blocks)
        
        # If still no code blocks, return the whole response
        return response