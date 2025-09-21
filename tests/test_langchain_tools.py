from langchain_tools.qtick import ServiceLookupInput


def test_service_lookup_input_allows_missing_business_filters():
    payload = ServiceLookupInput(service_name="babyhaircut")

    assert payload.business_id is None
    assert payload.business_name is None
    assert payload.limit == 5
