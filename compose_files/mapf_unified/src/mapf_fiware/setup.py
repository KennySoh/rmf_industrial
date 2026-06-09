from setuptools import find_packages, setup

package_name = "mapf_fiware"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
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
            "mapf_fiware = mapf_fiware.mapf_fiware:main",
            "movement_request_server_fiware = mapf_fiware.movement_request_server:main",
            "example  = mapf_fiware.example:main",
        ],
    },
)
