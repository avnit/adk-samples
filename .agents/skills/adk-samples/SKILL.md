```markdown
# adk-samples Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions used in the `adk-samples` Python repository. You'll learn the preferred file organization, import/export styles, commit message tendencies, and how to write and run tests. While no specific frameworks or automated workflows are detected, this guide will help you contribute code that fits seamlessly into the project.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - **Example:**  
    ```plaintext
    data_processor.py
    utils/helpers.py
    ```

### Import Style
- Use **relative imports** within the package.
  - **Example:**  
    ```python
    from .utils import helper_function
    from ..models import DataModel
    ```

### Export Style
- Use **named exports** (explicitly define what is exported).
  - **Example:**  
    ```python
    def useful_function():
        pass

    class ImportantClass:
        pass

    __all__ = ['useful_function', 'ImportantClass']
    ```

### Commit Patterns
- Commit messages are **freeform**, with no enforced prefix.
- Average commit message length is about 72 characters.
  - **Example:**  
    ```
    Fix bug in data parsing for edge cases
    ```

## Workflows

### Adding a New Sample Module
**Trigger:** When you want to add a new feature or example to the repository.  
**Command:** `/add-sample-module`

1. Create a new Python file using snake_case naming.
2. Implement your functions/classes.
3. Use relative imports for any internal dependencies.
4. Define `__all__` to specify exports.
5. Write corresponding test files (see Testing Patterns).
6. Commit your changes with a clear, concise message.

### Running Tests
**Trigger:** When you want to verify your code changes.  
**Command:** `/run-tests`

1. Locate test files matching the `*.test.*` pattern.
2. Run tests manually using your preferred Python test runner (e.g., `pytest`, `unittest`).
3. Review test results and fix any failures.

## Testing Patterns

- Test files follow the pattern `*.test.*` (e.g., `data_processor.test.py`).
- The testing framework is **unknown**; use standard Python testing practices.
- Place test files alongside or near the modules they test.
- Example test file:
  ```python
  # data_processor.test.py

  import unittest
  from .data_processor import useful_function

  class TestUsefulFunction(unittest.TestCase):
      def test_basic(self):
          self.assertEqual(useful_function(2), 4)

  if __name__ == '__main__':
      unittest.main()
  ```

## Commands
| Command             | Purpose                                    |
|---------------------|--------------------------------------------|
| /add-sample-module  | Scaffold and add a new sample module       |
| /run-tests          | Run all test files in the repository       |
```
