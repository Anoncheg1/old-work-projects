import pytest
from pydantic import ValidationError
from main import DistOneTableForm  # Import your actual module name

def test_field3_validation():
    # Test valid single email
    form = DistOneTableForm(field0=1, field1="valid_var", field2="/tmp", field3="test@example.com", action="add")
    assert form.field3 == "test@example.com"

    # Test valid list of emails
    form = DistOneTableForm(field0=1, field1="valid_var", field2="/tmp", field3="(email1@test.com email2@test.cm)", action="add")
    assert form.field3 == "(email1@test.com email2@test.cm)"

    # Test invalid single email
    with pytest.raises((ValueError, ValidationError)):
        DistOneTableForm(field0=1, field1="valid_var", field2="/tmp", field3="invalid_email", action="add")

    # Test invalid email in list
    with pytest.raises((ValueError, ValidationError)):
        DistOneTableForm(field0=1, field1="valid_var", field2="/tmp", field3="(valid@email.com invalid_email)", action="add")

    # Test malformed list (missing parentheses)
    with pytest.raises((ValueError, ValidationError)):
        DistOneTableForm(field0=1, field1="valid_var", field2="/tmp", field3="email1@test.com email2@test.com", action="add")

    # Test empty list
    with pytest.raises((ValueError, ValidationError)):
        DistOneTableForm(field0=1, field1="valid_var", field2="/tmp", field3="()", action="add")

    # Test list with one email
    form = DistOneTableForm(field0=1, field1="valid_var", field2="/tmp", field3="(single@email.com)", action="add")
    assert form.field3 == "(single@email.com)"

    # Test list with multiple emails and extra spaces
    form = DistOneTableForm(field0=1, field1="valid_var", field2="/tmp", field3="(  email1@test.com   email2@test.com  )", action="add")
    assert form.field3 == "(email1@test.com email2@test.com)"

test_field3_validation()
