"""Unit tests for lambdas/query-segments-info/."""

import importlib
import io
import json
from unittest.mock import MagicMock, patch

import requests
from moto import mock_aws

from conftest import load_lambda, load_module

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FAKE_LECTURE_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
FAKE_EMBEDDING  = [0.1] * 1024


class _FakeBedrockRuntime:
    """Plain stub for bedrock-runtime — same pattern as test_query_segments."""

    def __init__(self, embedding=None):
        self._embedding = embedding if embedding is not None else FAKE_EMBEDDING
        self.last_kwargs = {}

    def invoke_model(self, **kwargs):
        self.last_kwargs = kwargs
        body = json.dumps({"embedding": self._embedding}).encode()
        return {"body": io.BytesIO(body)}


# ---------------------------------------------------------------------------
# bedrock_utils tests
# ---------------------------------------------------------------------------


@mock_aws
class TestEmbedText:
    def setup_method(self, method):
        import constants
        importlib.reload(constants)
        self.mod = load_module("query-segments-info", "bedrock_utils")
        self.constants = constants

    def test_calls_invoke_model_with_correct_model_id(self):
        # The model ID string must reach the Bedrock API unchanged.
        fake = _FakeBedrockRuntime()
        model = self.constants.Model.AMAZON_TITAN_EMBED_IMAGE
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("hello", model, 1024)
        assert fake.last_kwargs["modelId"] == model.value

    def test_request_body_contains_input_text(self):
        # embed_text must forward the text as "inputText" for Titan.
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("lecture on neural nets", self.constants.Model.AMAZON_TITAN_EMBED_IMAGE, 1024)
        body = json.loads(fake.last_kwargs["body"])
        assert body["inputText"] == "lecture on neural nets"

    def test_request_body_contains_dimensions(self):
        # The requested embedding dimension must appear in the request body.
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("hello", self.constants.Model.AMAZON_TITAN_EMBED_IMAGE, 512)
        body = json.loads(fake.last_kwargs["body"])
        assert body["embeddingConfig"]["outputEmbeddingLength"] == 512

    def test_returns_embedding_vector(self):
        # The embedding list from Bedrock must be returned unchanged.
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            result = self.mod.embed_text("hello", self.constants.Model.AMAZON_TITAN_EMBED_IMAGE, 1024)
        assert result == FAKE_EMBEDDING


# ---------------------------------------------------------------------------
# aurora_utils tests
# ---------------------------------------------------------------------------


@mock_aws
class TestSearchSegments:
    def setup_method(self, method):
        self.mod = load_module("query-segments-info", "aurora_utils")

    def _prime_rds(self, records, column_metadata):
        """Queue a result set for the next moto execute_statement call."""
        resp = requests.post(
            "http://motoapi.amazonaws.com/moto-api/static/rds-data/statement-results",
            json={"results": [{"records": records, "columnMetadata": column_metadata}]},
        )
        assert resp.status_code == 201

    def _mock_rds(self):
        """Return a MagicMock rds_data client whose execute_statement returns empty results."""
        mock = MagicMock()
        mock.execute_statement.return_value = {"records": [], "columnMetadata": []}
        return mock

    def _full_column_metadata(self):
        return [
            {"label": "segment_id"},
            {"label": "start_s"},
            {"label": "end_s"},
            {"label": "idx"},
            {"label": "text"},
            {"label": "similarity"},
        ]

    def test_returns_a_list(self):
        result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 5)
        assert isinstance(result, list)

    def test_each_result_has_all_required_fields(self):
        # All six fields must be present in every result so the caller can
        # display transcript text, navigate by segment ID, and rank by score.
        self._prime_rds(
            column_metadata=self._full_column_metadata(),
            records=[[
                {"stringValue": "seg-1"},
                {"doubleValue": 0.0},
                {"doubleValue": 30.0},
                {"longValue": 0},
                {"stringValue": "Hello."},
                {"doubleValue": 0.9},
            ]],
        )
        result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 1)
        assert len(result) == 1
        assert set(result[0].keys()) == {"segmentId", "start", "end", "idx", "text", "similarity"}

    def test_k_is_forwarded_to_rds(self):
        mock_rds = self._mock_rds()
        with patch.object(self.mod, "rds_data", mock_rds):
            self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 7)
        params = {p["name"]: p["value"] for p in mock_rds.execute_statement.call_args.kwargs["parameters"]}
        assert params["k"] == {"longValue": 7}

    def test_video_uri_is_forwarded_to_rds(self):
        mock_rds = self._mock_rds()
        with patch.object(self.mod, "rds_data", mock_rds):
            self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 5)
        params = {p["name"]: p["value"] for p in mock_rds.execute_statement.call_args.kwargs["parameters"]}
        assert params["video_uri"] == {"stringValue": FAKE_LECTURE_ID}

    def test_embedding_vector_serialised_as_bracket_notation(self):
        mock_rds = self._mock_rds()
        small_vec = [0.5, -0.3, 1.0]
        with patch.object(self.mod, "rds_data", mock_rds):
            self.mod.search_segments(FAKE_LECTURE_ID, small_vec, 5)
        params = {p["name"]: p["value"] for p in mock_rds.execute_statement.call_args.kwargs["parameters"]}
        assert params["vec"] == {"stringValue": "[0.5,-0.3,1.0]"}

    def test_include_frames_true_does_not_filter_by_embedding_type(self):
        # When include_frames=True the SQL must search all embedding rows,
        # i.e. must NOT have an is_frame_embedding filter.
        mock_rds = self._mock_rds()
        with patch.object(self.mod, "rds_data", mock_rds):
            self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 5, include_frames=True)
        sql = mock_rds.execute_statement.call_args.kwargs["sql"]
        assert "is_frame_embedding" not in sql

    def test_include_frames_false_adds_text_only_filter(self):
        # When include_frames=False the SQL must restrict to text embeddings
        # only by filtering on is_frame_embedding = FALSE.
        mock_rds = self._mock_rds()
        with patch.object(self.mod, "rds_data", mock_rds):
            self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 5, include_frames=False)
        sql = mock_rds.execute_statement.call_args.kwargs["sql"]
        assert "is_frame_embedding" in sql

    def test_include_frames_defaults_to_true(self):
        # Calling without include_frames must behave the same as True.
        mock_rds = self._mock_rds()
        with patch.object(self.mod, "rds_data", mock_rds):
            self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 5)
        sql = mock_rds.execute_statement.call_args.kwargs["sql"]
        assert "is_frame_embedding" not in sql

    def test_rows_mapped_to_full_dicts(self):
        # Each DB row must be mapped to a dict with all six fields, with the
        # right types — floats for timestamps/similarity, int for idx, str
        # for segmentId and text.
        self._prime_rds(
            column_metadata=self._full_column_metadata(),
            records=[[
                {"stringValue": "seg-uuid-1"},
                {"doubleValue": 12.0},
                {"doubleValue": 28.0},
                {"longValue": 3},
                {"stringValue": "Hello world"},
                {"doubleValue": 0.95},
            ]],
        )
        result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 1)
        assert result == [{
            "segmentId":  "seg-uuid-1",
            "start":      12.0,
            "end":        28.0,
            "idx":        3,
            "text":       "Hello world",
            "similarity": 0.95,
        }]

    def test_multiple_rows_returned_in_order(self):
        # Results must preserve the similarity-DESC order produced by the SQL.
        self._prime_rds(
            column_metadata=self._full_column_metadata(),
            records=[
                [{"stringValue": "seg-1"}, {"doubleValue": 0.0},  {"doubleValue": 30.0}, {"longValue": 0}, {"stringValue": "A"}, {"doubleValue": 0.95}],
                [{"stringValue": "seg-2"}, {"doubleValue": 30.0}, {"doubleValue": 60.0}, {"longValue": 1}, {"stringValue": "B"}, {"doubleValue": 0.80}],
            ],
        )
        result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 2)
        assert len(result) == 2
        assert result[0]["segmentId"] == "seg-1"
        assert result[1]["segmentId"] == "seg-2"

    def test_similarity_is_float(self):
        self._prime_rds(
            column_metadata=self._full_column_metadata(),
            records=[[
                {"stringValue": "seg-1"}, {"doubleValue": 0.0}, {"doubleValue": 10.0},
                {"longValue": 0}, {"stringValue": "Hi"}, {"doubleValue": 0.87},
            ]],
        )
        result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 1)
        assert isinstance(result[0]["similarity"], float)
        assert result[0]["similarity"] == 0.87

    def test_idx_is_int(self):
        self._prime_rds(
            column_metadata=self._full_column_metadata(),
            records=[[
                {"stringValue": "seg-1"}, {"doubleValue": 0.0}, {"doubleValue": 10.0},
                {"longValue": 5}, {"stringValue": "Hi"}, {"doubleValue": 0.9},
            ]],
        )
        result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 1)
        assert isinstance(result[0]["idx"], int)
        assert result[0]["idx"] == 5


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


@mock_aws
class TestHandler:
    def setup_method(self, method):
        import constants
        importlib.reload(constants)
        load_module("query-segments-info", "bedrock_utils")
        load_module("query-segments-info", "aurora_utils")
        self.mod = load_lambda("query-segments-info")

    def _run(self, body=None):
        import bedrock_utils
        body = body or {"videoId": FAKE_LECTURE_ID, "query": "what is backpropagation"}
        fake = _FakeBedrockRuntime()
        with patch.object(bedrock_utils, "bedrock", fake):
            return self.mod.handler({"body": json.dumps(body)}, {})

    def test_returns_200(self):
        result = self._run()
        assert result["statusCode"] == 200

    def test_response_contains_segments_key(self):
        result = self._run()
        body = json.loads(result["body"])
        assert "segments" in body

    def test_segments_is_a_list(self):
        result = self._run()
        body = json.loads(result["body"])
        assert isinstance(body["segments"], list)

    def test_cors_headers_present(self):
        result = self._run()
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Headers" in result["headers"]
        assert "Access-Control-Allow-Methods" in result["headers"]

    def test_options_preflight_returns_200(self):
        result = self.mod.handler({"httpMethod": "OPTIONS", "body": None}, {})
        assert result["statusCode"] == 200

    def test_options_preflight_cors_headers(self):
        result = self.mod.handler({"httpMethod": "OPTIONS", "body": None}, {})
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "POST" in result["headers"]["Access-Control-Allow-Methods"]
        assert "OPTIONS" in result["headers"]["Access-Control-Allow-Methods"]

    def test_missing_video_id_returns_400(self):
        result = self._run({"query": "backpropagation"})
        assert result["statusCode"] == 400

    def test_missing_query_returns_400(self):
        result = self._run({"videoId": FAKE_LECTURE_ID})
        assert result["statusCode"] == 400

    def test_invalid_json_body_returns_400(self):
        import bedrock_utils
        fake = _FakeBedrockRuntime()
        with patch.object(bedrock_utils, "bedrock", fake):
            result = self.mod.handler({"body": "not json"}, {})
        assert result["statusCode"] == 400

    def test_k_out_of_range_returns_400(self):
        result = self._run({"videoId": FAKE_LECTURE_ID, "query": "neural nets", "k": 0})
        assert result["statusCode"] == 400

    def test_default_k_is_five(self):
        # Handler must pass k=5 to search_segments when not specified.
        calls = []

        def _spy(video_uri, embedding, k, include_frames):
            calls.append(k)
            return []

        with patch.object(self.mod, "search_segments", _spy):
            self._run()

        assert calls == [5]

    def test_custom_k_is_forwarded(self):
        calls = []

        def _spy(video_uri, embedding, k, include_frames):
            calls.append(k)
            return []

        with patch.object(self.mod, "search_segments", _spy):
            self._run({"videoId": FAKE_LECTURE_ID, "query": "neural nets", "k": 3})

        assert calls == [3]

    def test_include_frames_defaults_to_true(self):
        # Omitting includeFrames must default to True so frame embeddings
        # are included in the search unless the caller explicitly opts out.
        calls = []

        def _spy(video_uri, embedding, k, include_frames):
            calls.append(include_frames)
            return []

        with patch.object(self.mod, "search_segments", _spy):
            self._run()

        assert calls == [True]

    def test_include_frames_false_forwarded(self):
        # Passing includeFrames=false must restrict the search to text
        # embeddings only.
        calls = []

        def _spy(video_uri, embedding, k, include_frames):
            calls.append(include_frames)
            return []

        with patch.object(self.mod, "search_segments", _spy):
            self._run({"videoId": FAKE_LECTURE_ID, "query": "neural nets", "includeFrames": False})

        assert calls == [False]

    def test_segments_from_aurora_returned_verbatim(self):
        # Whatever search_segments returns must be forwarded as-is in the
        # response body — no stripping of fields like similarity or segmentId.
        fake_segments = [
            {"segmentId": "abc", "start": 10.0, "end": 20.0, "idx": 0, "text": "Hello", "similarity": 0.9},
        ]
        with patch.object(self.mod, "search_segments", return_value=fake_segments):
            result = self._run()
        body = json.loads(result["body"])
        assert body["segments"] == fake_segments

    def test_video_uri_constructed_from_bucket_and_video_id(self):
        # The handler must prepend "s3://{BUCKET_NAME}/" to the videoId
        # before passing it to search_segments.
        captured = []

        def _spy(video_uri, embedding, k, include_frames):
            captured.append(video_uri)
            return []

        with patch.object(self.mod, "search_segments", _spy):
            self._run({"videoId": "path/to/lecture.mp4", "query": "neural nets"})

        assert captured[0] == "s3://test-bucket/path/to/lecture.mp4"
