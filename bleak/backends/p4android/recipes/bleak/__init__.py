from pythonforandroid.recipe import PythonRecipe
from pythonforandroid.toolchain import shprint, info
from pythonforandroid.util import current_directory
from pythonforandroid import logger
import sh
from os.path import join
import os


class BleakRecipe(PythonRecipe):
    version = None
    url = None
    name = "bleak"
    # site_packages_name = 'bleak'

    src_filename = "/home/user/src/bleak"  #'src'

    depends = ["pyjnius"]
    call_hostpython_via_targetpython = False

    def prepare_build_dir(self, arch):
        shprint(sh.rm, "-rf", self.get_build_dir(arch))
        shprint(
            sh.ln,
            "-s",
            join(self.get_recipe_dir(), self.src_filename),
            self.get_build_dir(arch),
        )

    def should_build(self, arch):
        return True  # always rebuild?

    def get_recipe_env(self, arch=None, with_flags_in_cc=True):
        env = super().get_recipe_env(arch, with_flags_in_cc)
        # to find jnius and identify p4a
        env["PYJNIUS_PACKAGES"] = self.ctx.get_site_packages_dir()
        return env

    def postbuild_arch(self, arch):
        super().postbuild_arch(arch)

        info("Copying java files to dist_dir")

        # destdir = join(self.ctx.bootstrap.dist_dir, 'src', 'main', 'java')
        # destdir = join(self.ctx.bootstrap.distribution.dist_dir, 'src', 'main', 'java')
        destdir = self.ctx.javaclass_dir
        # os.makedirs(destdir, exist_ok=True)
        path = join(
            self.get_build_dir(arch.arch), "bleak", "backends", "p4android", "java", "."
        )

        shprint(sh.cp, "-a", path, destdir)


recipe = BleakRecipe()
