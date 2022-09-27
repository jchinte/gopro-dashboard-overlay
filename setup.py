import pathlib

from setuptools import setup
from setuptools.command.build_ext import build_ext
from setuptools.extension import Extension

HERE = pathlib.Path(__file__).parent

README = (HERE / "README.md").read_text()

requires = [
    "geotiler==0.14.5",
    "gpxpy==1.4.2",
    "geographiclib",
    "pillow==8.3.2",
    "pint==0.17",
    "progressbar2==3.53.3",
    "requests==2.27.1",
]

test_requirements = [
    "pytest"
]


class GoProOverlayBuildExt(build_ext):
    def build_extensions(self):
        print("I am here!")
        self.compiler.include_dirs = ["/usr/include/freetype2"] + self.compiler.include_dirs
        for extension in self.extensions:
            extension.libraries += [ "freetype" ]
            extension.extra_compile_args += [ "-ggdb", "-Wall", "-Werror" ]
            print(extension.libraries)

        build_ext.build_extensions(self)

setup(
    name="gopro-overlay",
    version="0.59.0",
    description="Overlay graphics dashboards onto GoPro footage",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/time4tea/gopro-dashboard-overlay",
    author="James Richardson",
    author_email="james+gopro@time4tea.net",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.10",
        "Environment :: Console",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Multimedia :: Video",
    ],
    packages=[
        "gopro_overlay",
        "gopro_overlay.icons",
        "gopro_overlay.layouts",
        "gopro_overlay.widgets",
    ],
    install_requires=requires,
    tests_require=test_requirements,
    scripts=[
        "bin/gopro-contrib-data-extract.py",
        "bin/gopro-cut.py",
        "bin/gopro-dashboard.py",
        "bin/gopro-extract.py",
        "bin/gopro-join.py",
        "bin/gopro-rename.py",
        "bin/gopro-to-csv.py",
        "bin/gopro-to-gpx.py",
    ],
    python_requires=">=3.8",
    include_package_data=True,
    entry_points={
        "console_scripts": []
    },
    project_urls={
        'Source': 'https://github.com/time4tea/gopro-dashboard-overlay',
    },
    cmdclass={"build_ext": GoProOverlayBuildExt},
    ext_modules=[Extension("gopro_overlay._freetype", ["c/freetype.c"])],
)
