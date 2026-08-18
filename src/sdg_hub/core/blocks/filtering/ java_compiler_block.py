# SPDX-License-Identifier: Apache-2.0
"""Java compiler/execution block for verifying generated design-pattern code."""

import os
import subprocess
import tempfile
from typing import Any, cast

from pydantic import Field
import pandas as pd

from ...utils.logger_config import setup_logger
from ..base import BaseBlock
from ..registry import BlockRegistry

logger = setup_logger(__name__)


@BlockRegistry.register(
    "JavaCompilerBlock",
    "filtering",
    "Compiles and executes generated Java code against a generated test "
    "driver, verifying the design pattern behaves as intended",
)
class JavaCompilerBlock(BaseBlock):
    block_type: str = "filtering"

    timeout: float = Field(
        15.0, description="Timeout in seconds for the compile and run steps"
    )

    def generate(self, samples: pd.DataFrame, **_kwargs: Any) -> pd.DataFrame:
        input_cols = cast(list[str], self.input_cols)
        source_col = input_cols[0]
        result_col = self.output_cols[0]
        success_col = f"{result_col}_success"

        results, successes = [], []
        for full_source in samples[source_col]:
            success, message = self._compile_and_run(full_source)
            successes.append(success)
            results.append(message)

        result = samples.copy()
        result[result_col] = results
        result[success_col] = successes
        return result

    def _compile_and_run(self, full_source: str) -> tuple[bool, str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, "Solution.java")
            with open(source_path, "w") as f:
                f.write(full_source)

            compile_result = subprocess.run(
                ["javac", "-d", tmpdir, source_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if compile_result.returncode != 0:
                return False, f"COMPILE_ERROR:\n{compile_result.stderr}"

            run_result = subprocess.run(
                ["java", "-cp", tmpdir, "GeneratedTest"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            success = run_result.returncode == 0
            message = run_result.stdout + run_result.stderr
            return success, message