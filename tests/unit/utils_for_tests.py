import base64
from pathlib import Path
from typing import Any

# from mbai.base.model import MBConnectionValues
from pydantic import BaseModel, ConfigDict, validate_call

# from mbai.aiserver.config import build_mb_connection_values


def create_dict_from_flat_str_keys(flat_dict: dict[str, Any]) -> dict:
    """very simple implementation of {"a.b.c" : 1, "a.b.d.":2} -> to nested dict
    there are no special cases implemented, numbers get converted to integers, only used for tests
    """
    res_dict = {}
    for k, v in flat_dict.items():
        cur_dict = res_dict
        keys = [x.strip() for x in k.split(".")]
        for sub_k in keys[:-1]:
            if sub_k.isnumeric():
                sub_k = int(sub_k)

            if sub_k not in cur_dict:
                cur_dict[sub_k] = {}
            cur_dict = cur_dict[sub_k]

        cur_dict[keys[-1]] = v

    return res_dict


def get_current_test_data_path() -> Path:
    current_path = Path(__file__).parent.resolve()
    test_data_path = current_path.parent / "data"
    assert test_data_path.is_dir(), f"something is wrong with the test_data_path = {test_data_path}"
    return test_data_path


class TestStrictBaseModel(BaseModel):
    """Base that makes LLM outputs stricter & cleaner."""

    model_config = ConfigDict(
        extra="forbid",  # disallow hallucinated keys
        use_enum_values=True,  # serialize enums as their values
        str_strip_whitespace=True,  # auto-trim strings
        validate_default=True,
        frozen=True,  # make instances immutable (nice for post-validation safety)
    )


@validate_call
def get_content_encoded(data_filepath: Path | str) -> str:
    with open(
        get_current_test_data_path() / data_filepath,
        "rb",
    ) as f:
        pdf_content_decoded = f.read()

    pdf_content_encoded = base64.b64encode(pdf_content_decoded).decode("utf-8")
    assert pdf_content_encoded is not None, "Could not open file."
    return pdf_content_encoded
