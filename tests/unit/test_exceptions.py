from mbai.base.exceptions import WrongImageFormatException, CustomException


def test_exceptions():
    a = 1
    b = "a"

    try:
        a + b
    except Exception as e:
        error_str = f"{type(e).__name__}: {e}"

    assert "TypeError" in error_str


def test_exceptions_convert():
    a = 1
    b = "a"

    try:
        a + b
    except Exception as e:
        error_str = CustomException.from_exception(e).get_msg()

    assert "TypeError" in error_str


def test_default_msg():

    exception = WrongImageFormatException()

    assert "WrongImageFormatException" in exception.get_msg()
    assert WrongImageFormatException.DEFAULT_MSG in exception.get_msg()


def test_custom_exception():

    exception = CustomException("my msg", data="first")

    assert "CustomException" in exception.get_msg()
