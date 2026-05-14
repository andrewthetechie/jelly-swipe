"""Tests for OpenAPI schema metadata and route exclusions."""

import pytest


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_openapi_endpoints_accessible(client, path):
    """Verify that /docs, /redoc, and /openapi.json are accessible."""
    response = client.get(path)
    assert response.status_code == 200, f"GET {path} returned {response.status_code}"


def test_openapi_metadata_present(client):
    """Verify that /openapi.json contains the configured title, version, description."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    # Check title
    assert schema.get("info", {}).get("title") == "Jellyswipe API"

    # Check version is present (not checking exact value yet, could be dev or package version)
    assert "version" in schema.get("info", {}), "Version missing from OpenAPI info"

    # Check description contains expected content
    description = schema.get("info", {}).get("description", "")
    assert description, "Description should be present"
    # We'll verify content in later tests

    # Check license_info
    assert schema.get("info", {}).get("license"), "License info missing"


def test_openapi_tags_present(client):
    """Verify that all 7 tags are present in the schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    tags = schema.get("tags", [])
    tag_names = {tag.get("name") for tag in tags}

    expected_tags = {
        "Authentication",
        "Rooms",
        "Swiping",
        "Matches",
        "Media",
        "Proxy",
        "Health",
    }
    assert expected_tags.issubset(tag_names), f"Missing tags. Have: {tag_names}"

    # Verify each tag has a description
    for tag in tags:
        if tag.get("name") in expected_tags:
            assert tag.get("description"), f"Tag {tag.get('name')} missing description"


def test_shared_schema_components_present(client):
    """OpenAPI components/schemas includes shared models ErrorResponse and MatchItem.

    CardItem is referenced only in endpoint descriptions (the deck route uses an
    untyped list response_model), so it does not appear as a top-level component.
    ErrorResponse and MatchItem are referenced by typed response_model declarations
    and must be present.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    components = schema.get("components", {}).get("schemas", {})

    for model_name in ("ErrorResponse", "MatchItem"):
        assert model_name in components, f"components/schemas missing '{model_name}'"


def test_static_routes_excluded_from_schema(client):
    """Verify that static routes are not in the OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    paths = schema.get("paths", {})
    excluded_paths = ["/", "/manifest.json", "/sw.js", "/favicon.ico"]

    for path in excluded_paths:
        assert path not in paths, f"Static route {path} should be excluded from schema"


def test_solo_room_route_excluded_from_schema(client):
    """Verify that POST /room/solo is excluded from schema but still returns 404 at runtime."""
    # Check it's not in the schema
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    paths = schema.get("paths", {})
    assert "/room/solo" not in paths, "POST /room/solo should be excluded from schema"

    # But it should still return 404 at runtime
    response = client.post("/room/solo", json={})
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"


def test_version_fallback_exists():
    """Verify that version is either from package or falls back to '0.0.0-dev'."""
    from jellyswipe.routers.health import __version__

    # Version should be non-empty string
    assert isinstance(__version__, str), "Version should be a string"
    assert len(__version__) > 0, "Version should not be empty"

    # Should be either a real version or the fallback
    assert __version__ == "0.0.0-dev" or "." in __version__ or __version__ == "unknown"


def test_auth_routes_have_authentication_tag(client):
    """Verify that all 4 auth routes are tagged under 'Authentication'."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    auth_routes = [
        ("/auth/jellyfin-use-server-identity", "post"),
        ("/auth/logout", "post"),
        ("/me", "get"),
        ("/jellyfin/server-info", "get"),
    ]

    for path, method in auth_routes:
        assert path in paths, f"Auth route {path} not in schema"
        route_spec = paths[path].get(method)
        assert route_spec is not None, f"{method.upper()} {path} not in schema"
        tags = route_spec.get("tags", [])
        assert "Authentication" in tags, (
            f"{method.upper()} {path} missing 'Authentication' tag"
        )


def test_auth_routes_have_response_models(client):
    """Verify that all 4 auth routes define response_model via schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    auth_routes = [
        ("/auth/jellyfin-use-server-identity", "post"),
        ("/auth/logout", "post"),
        ("/me", "get"),
        ("/jellyfin/server-info", "get"),
    ]

    for path, method in auth_routes:
        route_spec = paths[path].get(method)
        responses = route_spec.get("responses", {})
        # At least 200 should be present with a schema
        assert "200" in responses, f"{method.upper()} {path} missing 200 response"
        response_200 = responses["200"]
        assert "content" in response_200, (
            f"{method.upper()} {path} response has no content"
        )
        assert "application/json" in response_200.get("content", {}), (
            f"{method.upper()} {path} response has no JSON content"
        )


def test_auth_routes_have_error_responses(client):
    """Verify that protected auth routes document 401 error responses."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    # logout and /me require auth and should document 401
    protected_routes = [
        ("/auth/logout", "post"),
        ("/me", "get"),
    ]

    for path, method in protected_routes:
        route_spec = paths[path].get(method)
        responses = route_spec.get("responses", {})
        assert "401" in responses, (
            f"{method.upper()} {path} should document 401 response"
        )


def test_auth_routes_have_summaries(client):
    """Verify that all auth routes have short summary descriptions."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    auth_routes = [
        ("/auth/jellyfin-use-server-identity", "post"),
        ("/auth/logout", "post"),
        ("/me", "get"),
        ("/jellyfin/server-info", "get"),
    ]

    for path, method in auth_routes:
        route_spec = paths[path].get(method)
        summary = route_spec.get("summary")
        assert summary is not None and len(summary) > 0, (
            f"{method.upper()} {path} missing or empty summary"
        )
        # Summary should be relatively short (one line)
        assert len(summary) < 150, (
            f"{method.upper()} {path} summary too long (should be one-liner)"
        )


def test_auth_routes_have_descriptions(client):
    """Verify that all auth routes have detailed descriptions for ReDoc."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    auth_routes = [
        ("/auth/jellyfin-use-server-identity", "post"),
        ("/auth/logout", "post"),
        ("/me", "get"),
        ("/jellyfin/server-info", "get"),
    ]

    for path, method in auth_routes:
        route_spec = paths[path].get(method)
        description = route_spec.get("description")
        assert description is not None and len(description) > 0, (
            f"{method.upper()} {path} missing or empty description"
        )


def test_health_routes_have_health_tag(client):
    """Verify that /healthz and /readyz are tagged under 'Health'."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    health_routes = [
        ("/healthz", "get"),
        ("/readyz", "get"),
    ]

    for path, method in health_routes:
        assert path in paths, f"Health route {path} not in schema"
        route_spec = paths[path].get(method)
        assert route_spec is not None, f"{method.upper()} {path} not in schema"
        tags = route_spec.get("tags", [])
        assert "Health" in tags, f"{method.upper()} {path} missing 'Health' tag"


def test_health_routes_have_summaries(client):
    """Verify that both health routes have short summary descriptions."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    health_routes = [
        ("/healthz", "get"),
        ("/readyz", "get"),
    ]

    for path, method in health_routes:
        route_spec = paths[path].get(method)
        summary = route_spec.get("summary")
        assert summary is not None and len(summary) > 0, (
            f"{method.upper()} {path} missing or empty summary"
        )


def test_health_routes_have_descriptions(client):
    """Verify that both health routes have detailed descriptions for ReDoc."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    health_routes = [
        ("/healthz", "get"),
        ("/readyz", "get"),
    ]

    for path, method in health_routes:
        route_spec = paths[path].get(method)
        description = route_spec.get("description")
        assert description is not None and len(description) > 0, (
            f"{method.upper()} {path} missing or empty description"
        )


def test_readyz_documents_503_response(client):
    """Verify that /readyz documents its 503 failure response."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    readyz_spec = paths["/readyz"].get("get")
    responses = readyz_spec.get("responses", {})
    assert "503" in responses, "/readyz should document 503 response for degraded state"


# ---------------------------------------------------------------------------
# Rooms lifecycle route metadata
# ---------------------------------------------------------------------------

LIFECYCLE_ROUTES = [
    ("/room", "post"),
    ("/room/{code}/join", "post"),
    ("/room/{code}/status", "get"),
    ("/room/{code}/quit", "post"),
]


def test_rooms_routes_have_rooms_tag(client):
    """All 4 room lifecycle routes carry the 'Rooms' tag."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in LIFECYCLE_ROUTES:
        spec = paths[path][method]
        assert "Rooms" in spec.get("tags", []), (
            f"{method.upper()} {path} missing 'Rooms' tag"
        )


def test_rooms_routes_have_summaries(client):
    """All 4 room lifecycle routes carry a non-empty summary."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in LIFECYCLE_ROUTES:
        spec = paths[path][method]
        assert spec.get("summary"), f"{method.upper()} {path} missing summary"


def test_rooms_routes_have_descriptions(client):
    """All 4 room lifecycle routes carry a non-empty description (docstring)."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in LIFECYCLE_ROUTES:
        spec = paths[path][method]
        assert spec.get("description"), f"{method.upper()} {path} missing description"


def test_rooms_routes_have_response_models(client):
    """All 4 room lifecycle routes define a typed 200 response schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in LIFECYCLE_ROUTES:
        spec = paths[path][method]
        responses = spec.get("responses", {})
        assert "200" in responses, f"{method.upper()} {path} missing 200 response"
        content = responses["200"].get("content", {})
        assert "application/json" in content, (
            f"{method.upper()} {path} 200 response has no JSON content"
        )


def test_post_room_documents_422_response(client):
    """POST /room documents a 422 response for malformed body."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    post_room = paths["/room"]["post"]
    assert "422" in post_room.get("responses", {}), (
        "POST /room should document 422 for validation errors"
    )


def test_post_room_body_schema_has_boolean_fields(client):
    """POST /room request body schema documents movies, tv_shows, solo as booleans."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})
    components = schema.get("components", {}).get("schemas", {})

    post_room = paths["/room"]["post"]
    request_body = post_room.get("requestBody", {})
    assert request_body, "POST /room missing requestBody"
    json_content = request_body.get("content", {}).get("application/json", {})
    body_schema = json_content.get("schema", {})
    assert body_schema, "POST /room requestBody has no schema"

    # FastAPI wraps optional body in anyOf with null; find the $ref entry
    if "anyOf" in body_schema:
        refs = [e for e in body_schema["anyOf"] if "$ref" in e]
        assert refs, "POST /room body anyOf has no $ref to a named schema"
        body_schema = refs[0]

    # Follow $ref to the named component schema
    if "$ref" in body_schema:
        ref_name = body_schema["$ref"].split("/")[-1]
        body_schema = components[ref_name]

    properties = body_schema.get("properties", {})
    for field in ("movies", "tv_shows", "solo"):
        assert field in properties, f"POST /room body missing '{field}' property"
        assert properties[field].get("type") == "boolean", (
            f"POST /room body '{field}' should be typed as boolean, got {properties[field]}"
        )


# ---------------------------------------------------------------------------
# Swiping route metadata
# ---------------------------------------------------------------------------

SWIPING_ROUTES = [
    ("/room/{code}/swipe", "post"),
    ("/room/{code}/undo", "post"),
    ("/room/{code}/genre", "post"),
    ("/room/{code}/watched-filter", "post"),
    ("/room/{code}/deck", "get"),
]


def test_swiping_routes_have_swiping_tag(client):
    """All 5 in-room action routes carry the 'Swiping' tag."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in SWIPING_ROUTES:
        spec = paths[path][method]
        assert "Swiping" in spec.get("tags", []), (
            f"{method.upper()} {path} missing 'Swiping' tag"
        )


def test_swiping_routes_have_summaries(client):
    """All 5 in-room action routes carry a non-empty summary."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in SWIPING_ROUTES:
        spec = paths[path][method]
        assert spec.get("summary"), f"{method.upper()} {path} missing summary"


def test_swiping_routes_have_descriptions(client):
    """All 5 in-room action routes carry a non-empty description (docstring)."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in SWIPING_ROUTES:
        spec = paths[path][method]
        assert spec.get("description"), f"{method.upper()} {path} missing description"


def test_swiping_routes_have_response_models(client):
    """All 5 in-room action routes define a typed 200 response schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in SWIPING_ROUTES:
        spec = paths[path][method]
        responses = spec.get("responses", {})
        assert "200" in responses, f"{method.upper()} {path} missing 200 response"
        content = responses["200"].get("content", {})
        assert "application/json" in content, (
            f"{method.upper()} {path} 200 response has no JSON content"
        )


def test_swipe_post_documents_typed_request_body(client):
    """POST /room/{code}/swipe documents a typed requestBody with media_id."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    swipe_spec = paths["/room/{code}/swipe"]["post"]
    request_body = swipe_spec.get("requestBody", {})
    assert request_body, "POST /room/{code}/swipe missing requestBody"
    json_schema = (
        request_body.get("content", {}).get("application/json", {}).get("schema", {})
    )
    assert json_schema, "POST /room/{code}/swipe requestBody has no schema"


def test_swipe_post_documents_404_response(client):
    """POST /room/{code}/swipe documents a 404 error response."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    swipe_spec = paths["/room/{code}/swipe"]["post"]
    assert "404" in swipe_spec.get("responses", {}), (
        "POST /room/{code}/swipe should document 404 response"
    )


# ---------------------------------------------------------------------------
# Matches route metadata
# ---------------------------------------------------------------------------

MATCHES_ROUTES = [
    ("/matches", "get"),
    ("/matches/delete", "post"),
]


def test_matches_routes_have_matches_tag(client):
    """Both matches routes carry the 'Matches' tag."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in MATCHES_ROUTES:
        spec = paths[path][method]
        assert "Matches" in spec.get("tags", []), (
            f"{method.upper()} {path} missing 'Matches' tag"
        )


def test_matches_routes_have_summaries(client):
    """Both matches routes carry a non-empty summary."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in MATCHES_ROUTES:
        spec = paths[path][method]
        assert spec.get("summary"), f"{method.upper()} {path} missing summary"


def test_matches_routes_have_descriptions(client):
    """Both matches routes carry a non-empty description (docstring)."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in MATCHES_ROUTES:
        spec = paths[path][method]
        assert spec.get("description"), f"{method.upper()} {path} missing description"


def test_matches_routes_have_response_models(client):
    """Both matches routes define a typed 200 response schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in MATCHES_ROUTES:
        spec = paths[path][method]
        responses = spec.get("responses", {})
        assert "200" in responses, f"{method.upper()} {path} missing 200 response"
        content = responses["200"].get("content", {})
        assert "application/json" in content, (
            f"{method.upper()} {path} 200 response has no JSON content"
        )


def test_get_matches_documents_view_query_parameter(client):
    """GET /matches documents the 'view' query parameter with valid values."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    spec = paths["/matches"]["get"]
    params = {p["name"]: p for p in spec.get("parameters", [])}
    assert "view" in params, "GET /matches missing 'view' query parameter"
    view_schema = params["view"].get("schema", {})
    # FastAPI renders Optional[Literal["history"]] as anyOf with a const entry
    any_of = view_schema.get("anyOf", [])
    valid_values = {e.get("const") or e.get("enum", [None])[0] for e in any_of}
    valid_values.discard(None)
    assert "history" in valid_values, (
        "GET /matches 'view' param should document 'history' as a valid value"
    )


def test_delete_match_post_documents_typed_request_body(client):
    """POST /matches/delete documents a typed requestBody with media_id."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    spec = paths["/matches/delete"]["post"]
    request_body = spec.get("requestBody", {})
    assert request_body, "POST /matches/delete missing requestBody"
    json_schema = (
        request_body.get("content", {}).get("application/json", {}).get("schema", {})
    )
    assert json_schema, "POST /matches/delete requestBody has no schema"


# ---------------------------------------------------------------------------
# Media route metadata
# ---------------------------------------------------------------------------

MEDIA_ROUTES = [
    ("/get-trailer/{movie_id}", "get"),
    ("/cast/{movie_id}", "get"),
    ("/genres", "get"),
    ("/watchlist/add", "post"),
]


def test_media_routes_have_media_tag(client):
    """All 4 media routes carry the 'Media' tag."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in MEDIA_ROUTES:
        spec = paths[path][method]
        assert "Media" in spec.get("tags", []), (
            f"{method.upper()} {path} missing 'Media' tag"
        )


def test_media_routes_have_summaries(client):
    """All 4 media routes define a non-empty summary."""
    response = client.get("/openapi.json")
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in MEDIA_ROUTES:
        spec = paths[path][method]
        assert spec.get("summary"), f"{method.upper()} {path} missing summary"


def test_media_routes_have_descriptions(client):
    """All 4 media routes define a non-empty description (docstring)."""
    response = client.get("/openapi.json")
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in MEDIA_ROUTES:
        spec = paths[path][method]
        assert spec.get("description"), f"{method.upper()} {path} missing description"


def test_media_routes_have_response_models(client):
    """All 4 media routes define a typed 200 response schema."""
    response = client.get("/openapi.json")
    schema = response.json()
    paths = schema.get("paths", {})

    for path, method in MEDIA_ROUTES:
        spec = paths[path][method]
        responses = spec.get("responses", {})
        assert "200" in responses, f"{method.upper()} {path} missing 200 response"
        content = responses["200"].get("content", {})
        assert "application/json" in content, (
            f"{method.upper()} {path} 200 response has no JSON content"
        )


def test_trailer_route_documents_404_and_502(client):
    """GET /get-trailer/{movie_id} documents 404 and 502 error responses."""
    response = client.get("/openapi.json")
    schema = response.json()
    responses = schema["paths"]["/get-trailer/{movie_id}"]["get"]["responses"]
    assert "404" in responses, "trailer route missing 404 documentation"
    assert "502" in responses, "trailer route missing 502 documentation"


def test_cast_route_documents_404_and_502(client):
    """GET /cast/{movie_id} documents 404 and 502 error responses."""
    response = client.get("/openapi.json")
    schema = response.json()
    responses = schema["paths"]["/cast/{movie_id}"]["get"]["responses"]
    assert "404" in responses, "cast route missing 404 documentation"
    assert "502" in responses, "cast route missing 502 documentation"


def test_watchlist_post_documents_typed_request_body(client):
    """POST /watchlist/add documents a typed request body with media_id."""
    response = client.get("/openapi.json")
    schema = response.json()
    spec = schema["paths"]["/watchlist/add"]["post"]
    request_body = spec.get("requestBody", {})
    assert request_body, "watchlist/add missing requestBody"
    content = request_body.get("content", {})
    assert "application/json" in content, "watchlist/add requestBody has no JSON schema"


# ---------------------------------------------------------------------------
# Proxy Endpoint Documentation Tests
# ---------------------------------------------------------------------------


def test_proxy_route_has_proxy_tag(client):
    """GET /proxy has 'Proxy' tag in OpenAPI schema."""
    response = client.get("/openapi.json")
    schema = response.json()
    tags = schema["paths"]["/proxy"]["get"].get("tags", [])
    assert "Proxy" in tags, f"proxy route missing Proxy tag, got tags: {tags}"


def test_proxy_route_has_summary(client):
    """GET /proxy has a summary in OpenAPI schema."""
    response = client.get("/openapi.json")
    schema = response.json()
    summary = schema["paths"]["/proxy"]["get"].get("summary")
    assert summary, "proxy route missing summary"


def test_proxy_route_has_description(client):
    """GET /proxy has a description/docstring in OpenAPI schema."""
    response = client.get("/openapi.json")
    schema = response.json()
    description = schema["paths"]["/proxy"]["get"].get("description")
    assert description, "proxy route missing description"
    # Should mention the URL form and that it returns images
    assert "jellyfin" in description.lower() or "path" in description.lower(), (
        "proxy route description should document the path parameter format"
    )


def test_proxy_route_documents_200_response_with_image_content(client):
    """GET /proxy documents 200 response with image/* content type."""
    response = client.get("/openapi.json")
    schema = response.json()
    responses = schema["paths"]["/proxy"]["get"]["responses"]
    assert "200" in responses, "proxy route missing 200 response documentation"

    response_200 = responses["200"]
    content = response_200.get("content", {})

    # Should declare image/* as the content type, not application/json
    assert (
        "image/*" in content
        or "image/png" in content
        or "image/jpeg" in content
        or "image/webp" in content
    ), (
        f"proxy route 200 response should declare image content type, got: {list(content.keys())}"
    )


def test_proxy_route_documents_403_404_502_errors(client):
    """GET /proxy documents 403, 404, 502 error responses."""
    response = client.get("/openapi.json")
    schema = response.json()
    responses = schema["paths"]["/proxy"]["get"]["responses"]

    for status in ["403", "404", "502"]:
        assert status in responses, f"proxy route missing {status} documentation"
        # Each error should reference ErrorResponse model
        response_spec = responses[status]
        content = response_spec.get("content", {}).get("application/json", {})
        schema_ref = content.get("schema", {})

        # Check if it references ErrorResponse
        if "$ref" in schema_ref:
            assert "ErrorResponse" in schema_ref["$ref"], (
                f"{status} response should reference ErrorResponse, got: {schema_ref['$ref']}"
            )


def test_proxy_route_documents_path_query_parameter(client):
    """GET /proxy documents the 'path' query parameter."""
    response = client.get("/openapi.json")
    schema = response.json()
    spec = schema["paths"]["/proxy"]["get"]

    parameters = spec.get("parameters", [])
    assert parameters, "proxy route missing parameters documentation"

    path_param = None
    for param in parameters:
        if param.get("name") == "path":
            path_param = param
            break

    assert path_param, "proxy route missing 'path' query parameter documentation"
    assert path_param.get("in") == "query", "'path' should be a query parameter"
    # Note: parameter is technically optional in FastAPI to avoid 422 on missing path,
    # but semantically required by the endpoint logic (returns 403 if missing)
    assert path_param.get("description"), "'path' parameter should have a description"


# ---------------------------------------------------------------------------
# SSE stream route metadata
# ---------------------------------------------------------------------------


def test_stream_route_has_rooms_tag(client):
    """GET /room/{code}/stream carries the 'Rooms' tag."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    spec = schema["paths"]["/room/{code}/stream"]["get"]
    assert "Rooms" in spec.get("tags", []), "stream route missing 'Rooms' tag"


def test_stream_route_has_summary(client):
    """GET /room/{code}/stream carries a non-empty summary."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    spec = schema["paths"]["/room/{code}/stream"]["get"]
    assert spec.get("summary"), "stream route missing summary"


def test_stream_route_has_description_with_sse_link(client):
    """GET /room/{code}/stream description links to docs/sse-events.md."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    spec = schema["paths"]["/room/{code}/stream"]["get"]
    description = spec.get("description", "")
    assert description, "stream route missing description"
    assert "sse-events.md" in description, (
        "stream route description should link to docs/sse-events.md"
    )


def test_sse_events_doc_exists():
    """docs/sse-events.md exists at the repo root under docs/."""
    from pathlib import Path

    repo_root = Path(__file__).parent.parent
    doc_path = repo_root / "docs" / "sse-events.md"
    assert doc_path.exists(), f"docs/sse-events.md not found at {doc_path}"
