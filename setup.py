"""Include editable YAML configuration in built wheels without a second source copy."""
from pathlib import Path
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        shutil.copytree(Path(__file__).parent / "configs", Path(self.build_lib) / "secprbench/configs",
                        dirs_exist_ok=True)


setup(cmdclass={"build_py": BuildPy})
