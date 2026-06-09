import yaml

from adg.models.plan_models import GlobalPlan


def read_yaml(file_path: str):
    with open(file_path, "r") as stream:
        config = yaml.safe_load(stream)

    return GlobalPlan(**config)
