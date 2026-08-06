```markdown
# adk-samples Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions used in the `adk-samples` Python repository. You'll learn about file naming, import/export styles, commit conventions, and how to structure and run tests. This guide is ideal for contributors who want to maintain consistency and quality in the codebase.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `data_loader.py`, `process_utils.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import helper_function
    ```

### Export Style
- Use **named exports** (explicitly define what is exported).
  - Example:
    ```python
    def important_function():
        pass

    __all__ = ['important_function']
    ```

### Commit Patterns
- Commit messages are **freeform** (no strict prefix required).
- Average commit message length: ~70 characters.
  - Example:  
    ```
    Add support for new data format in loader module
    ```

## Workflows

### Adding a New Module
**Trigger:** When you need to add a new feature or utility module  
**Command:** `/add-module`

1. Create a new Python file using snake_case (e.g., `new_feature.py`).
2. Implement your functions/classes.
3. Use relative imports to reference other modules.
4. Define `__all__` for named exports.
5. Write corresponding test files (see Testing Patterns).
6. Commit changes with a clear, descriptive message.

### Running Tests
**Trigger:** When you want to verify code correctness  
**Command:** `/run-tests`

1. Identify test files (pattern: `*.test.*`).
2. Use the project's preferred test runner (framework unknown; try `pytest` or `unittest`).
   - Example:
     ```
     pytest
     ```
3. Review test output and fix any failures.

## Testing Patterns

- Test files follow the pattern: `*.test.*` (e.g., `data_loader.test.py`).
- The specific testing framework is **unknown**; try running with common Python test runners.
- Place test files alongside the modules they test or in a dedicated `tests/` directory.
- Example test file structure:
  ```python
  import unittest
  from .data_loader import load_data

  class TestDataLoader(unittest.TestCase):
      def test_load_data(self):
          result = load_data('test.csv')
          self.assertIsNotNone(result)
  ```

## Commands
| Command      | Purpose                                |
|--------------|----------------------------------------|
| /add-module  | Scaffold and add a new module          |
| /run-tests   | Run all test files in the repository   |
```
