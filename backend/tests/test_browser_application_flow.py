from app.services.browser_assistance import _field_from_raw, suggest_profile_key


def test_select_field_exposes_bounded_options():
    field = _field_from_raw({
        "field_id": "cm-field-1", "label": "Work arrangement", "kind": "select",
        "required": True, "options": [
            {"label": "Hybrid", "value": "hybrid"},
            {"label": "Remote", "value": "remote"},
        ],
    })
    assert field is not None
    assert field.kind == "select"
    assert field.required is True
    assert field.options == [
        {"label": "Hybrid", "value": "hybrid"},
        {"label": "Remote", "value": "remote"},
    ]


def test_sensitive_form_fields_are_never_suggested():
    assert _field_from_raw({
        "field_id": "cm-field-1", "label": "Passport number", "kind": "text"
    }) is None


def test_experience_and_education_labels_map_to_cv_profile():
    assert suggest_profile_key("Professional experience") == "experience"
    assert suggest_profile_key("Education history") == "education"
    assert suggest_profile_key("Technical skills") == "skills"
