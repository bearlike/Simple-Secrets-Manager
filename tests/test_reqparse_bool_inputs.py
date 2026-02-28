from flask_restx import reqparse, inputs


def _convert_with(parser, name: str, value: str):
    argument = next(item for item in parser.args if item.name == name)
    return argument.convert(value, None)


def test_default_bool_type_misparses_false_string():
    parser = reqparse.RequestParser()
    parser.add_argument("flag", type=bool, default=False, location="args")
    assert _convert_with(parser, "flag", "false") is True


def test_inputs_boolean_parses_false_and_true_strings():
    parser = reqparse.RequestParser()
    parser.add_argument(
        "flag", type=inputs.boolean, default=False, location="args"
    )
    assert _convert_with(parser, "flag", "false") is False
    assert _convert_with(parser, "flag", "true") is True
