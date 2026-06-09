from setuptools import find_packages, setup
import os
from glob import glob

package_name = "fiware_map"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "maps"), glob("maps/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="rosi",
    maintainer_email="glenn_tan@artc.a-star.edu.sg",
    description="TODO: Package description",
    license="TODO: License declaration",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "fiware_map_server = fiware_map.fiware_map:main",
            "load_maps = fiware_map.fiware_client:main",
            "example_consumer = fiware_map.example_consumer:main",
        ],
    },
)
