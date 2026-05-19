from mbai.aiserver.utils.general_utils import get_current_utc_ts_iso_z, number_in_range
from mbai.aiserver.utils.llm_parsing_utils import LLMStrParsingUtils


def test_get_ts():
    ts = get_current_utc_ts_iso_z()

    assert len(ts) > 20, f"seems incorrect: {ts=}"
    assert "T" in ts and "Z" in ts, f"seems incorrect: {ts=}"


def test_number_in_range():

    assert number_in_range(1, 1, 5)
    assert number_in_range(3, 1, 5)
    assert number_in_range(5, 1, 5)
    assert number_in_range(2, 1, 5)
    assert number_in_range(1, 2, 5) == False
    assert number_in_range(4, 110, 300) == False
    assert number_in_range(500, 1100, 300) == False
    assert number_in_range(500, 1100, None) == False
    assert number_in_range(None, None, None) == False
    assert number_in_range(None, 1, 2) == False
    assert number_in_range(1, None, 2) == False


def test_cleanup_extracts_from_json_code_block():
    raw = """
```json{"a":1}```
"""
    result = LLMStrParsingUtils._cleanup_llm_json_str(raw)
    assert result == '{"a":1}'


def test_cleanup_extracts_from_unmarked_code_block():
    raw = """
```{"a":1}``` }
"""
    result = LLMStrParsingUtils._cleanup_llm_json_str(raw)
    assert result == '{"a":1}'


def test_cleanup_extracts_json_without_code_block():
    raw = """
    `{"a":1}` {
"""
    result = LLMStrParsingUtils._cleanup_llm_json_str(raw)
    # Falls back to finding { and }, gets the valid JSON object
    assert result == '{"a":1}'


def test_extract_handles_trailing_comma():
    raw = """
    this is my json: {"a":1,} 
"""
    result = LLMStrParsingUtils.extract_json_obj_from_llm_output(raw)
    assert result == {"a": 1}


def test_extract_handles_clean_json():
    raw = '{"name": "test", "value": 42}'
    result = LLMStrParsingUtils.extract_json_obj_from_llm_output(raw)
    assert result == {"name": "test", "value": 42}


def test_extract_handles_non_breaking_spaces():
    raw = '{"key":\xa0"value"}'
    result = LLMStrParsingUtils.extract_json_obj_from_llm_output(raw)
    assert result == {"key": "value"}


def test_extract_handles_nested_objects():
    raw = '```json\n{"outer": {"inner": 123}}\n```'
    result = LLMStrParsingUtils.extract_json_obj_from_llm_output(raw)
    assert result == {"outer": {"inner": 123}}
