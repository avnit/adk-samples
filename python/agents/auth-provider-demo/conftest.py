"""Make the ``auth_provider_demo`` package importable during test collection.

CI runs ``pytest`` from the repository root without installing this sample as a
package, so ``import auth_provider_demo`` would otherwise fail. pytest imports
this conftest (the nearest one to the test files) before collecting the tests,
and adding this directory to ``sys.path`` here makes the package importable
regardless of the working directory pytest was launched from.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
