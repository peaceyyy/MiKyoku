"""
Unit tests for Phase 2: trace.moe service and AniList direct ID lookup.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.anilist_service import fetch_anime_info, fetch_anime_info_by_id
from services.tracemoe_service import (
    DEFAULT_TRACE_MOE_THRESHOLD,
    TRACE_MOE_API_URL,
    TraceMoeResult,
    get_tracemoe_api_key,
    get_tracemoe_threshold,
    identify_via_tracemoe,
    is_tracemoe_enabled,
)


def _make_mock_httpx_client(response=None, side_effect=None):
    """Build an AsyncMock context-managed httpx.AsyncClient."""
    mock_client = AsyncMock()
    if side_effect is not None:
        mock_client.post = AsyncMock(side_effect=side_effect)
    else:
        mock_client.post = AsyncMock(return_value=response)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm, mock_client


def _make_response(status_code=200, json_data=None, json_exc=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.text = text
    if json_exc is not None:
        resp.json = MagicMock(side_effect=json_exc)
    else:
        resp.json = MagicMock(return_value=json_data)
    return resp


class TestPhase2TraceMoeService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._env_patcher = patch.dict(os.environ, {}, clear=False)
        self._env_patcher.start()
        for key in ("TRACE_MOE_API_KEY", "TRACE_MOE_THRESHOLD", "TRACE_MOE_ENABLED"):
            os.environ.pop(key, None)

    def tearDown(self):
        self._env_patcher.stop()

    async def test_tracemoe_high_confidence_int_anilist(self):
        payload = {
            "frameCount": 12345,
            "error": "",
            "result": [
                {
                    "anilist": 154587,
                    "filename": "Frieren - 01.mp4",
                    "episode": 1,
                    "from": 120.5,
                    "to": 122.0,
                    "similarity": 0.94,
                }
            ],
        }
        mock_cm, mock_client = _make_mock_httpx_client(response=_make_response(200, payload))

        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            result = await identify_via_tracemoe(b"img-bytes", mime_type="image/png", min_similarity=0.88)

        self.assertIsNotNone(result)
        self.assertEqual(result.anilist_id, 154587)
        self.assertAlmostEqual(result.similarity, 0.94)
        self.assertEqual(result.episode, 1)
        self.assertAlmostEqual(result.from_sec, 120.5)
        self.assertAlmostEqual(result.to_sec, 122.0)
        self.assertEqual(result.filename, "Frieren - 01.mp4")

        mock_client.post.assert_awaited_once()
        call_args, call_kwargs = mock_client.post.call_args
        self.assertEqual(call_args[0], TRACE_MOE_API_URL)
        self.assertEqual(call_kwargs["params"], {"cutBorders": "", "anilistInfo": ""})
        self.assertEqual(call_kwargs["headers"]["Content-Type"], "image/png")
        self.assertNotIn("x-trace-key", call_kwargs["headers"])

    async def test_tracemoe_high_confidence_dict_anilist(self):
        payload = {
            "error": "",
            "result": [
                {
                    "anilist": {"id": 21, "isAdult": False},
                    "episode": 1015,
                    "similarity": 0.91,
                }
            ],
        }
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(200, payload))

        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            result = await identify_via_tracemoe(b"img-bytes", min_similarity=0.88)

        self.assertIsNotNone(result)
        self.assertEqual(result.anilist_id, 21)
        self.assertFalse(result.is_adult)

    async def test_tracemoe_legacy_anilist_id_fallback(self):
        payload = {
            "error": "",
            "result": [
                {
                    "anilist_id": 9253,
                    "episode": 5,
                    "similarity": 0.90,
                }
            ],
        }
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(200, payload))

        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            result = await identify_via_tracemoe(b"img-bytes", min_similarity=0.88)

        self.assertIsNotNone(result)
        self.assertEqual(result.anilist_id, 9253)

    async def test_tracemoe_below_threshold_returns_none(self):
        payload = {
            "error": "",
            "result": [{"anilist": 1, "similarity": 0.82}],
        }
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(200, payload))

        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            result = await identify_via_tracemoe(b"img-bytes", min_similarity=0.88)

        self.assertIsNone(result)

    async def test_tracemoe_empty_bytes_skips_network_call(self):
        with patch("services.tracemoe_service.httpx.AsyncClient") as mock_client_cls:
            result = await identify_via_tracemoe(b"")

        self.assertIsNone(result)
        mock_client_cls.assert_not_called()

    async def test_tracemoe_rate_limit_429_returns_none(self):
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(429, text="Too Many Requests"))

        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            result = await identify_via_tracemoe(b"img-bytes")

        self.assertIsNone(result)

    async def test_tracemoe_server_error_500_returns_none(self):
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(500, text="Internal Server Error"))

        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            result = await identify_via_tracemoe(b"img-bytes")

        self.assertIsNone(result)

    async def test_tracemoe_timeout_and_request_error_return_none(self):
        for exc in (httpx.ReadTimeout("timed out"), httpx.ConnectError("dns failed"), RuntimeError("boom")):
            with self.subTest(exc=type(exc).__name__):
                mock_cm, _ = _make_mock_httpx_client(side_effect=exc)
                with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
                    result = await identify_via_tracemoe(b"img-bytes")
                self.assertIsNone(result)

    async def test_tracemoe_malformed_responses_return_none(self):
        bad_responses = [
            _make_response(200, json_exc=ValueError("bad json")),
            _make_response(200, json_data=["unexpected-list"]),
            _make_response(200, json_data={"error": "Quota exceeded", "result": []}),
            _make_response(200, json_data={"error": "", "result": []}),
            _make_response(200, json_data={"error": "", "result": [{"anilist": 1, "similarity": float("nan")}]}),
        ]
        for resp in bad_responses:
            mock_cm, _ = _make_mock_httpx_client(response=resp)
            with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
                result = await identify_via_tracemoe(b"img-bytes")
            self.assertIsNone(result)

    async def test_tracemoe_sorts_defensively_and_skips_bad_entries(self):
        payload = {
            "error": "",
            "result": [
                {"anilist": 100, "similarity": 0.89},
                {"anilist": -1, "similarity": 0.99},
                {"anilist": 200, "similarity": "not-a-float"},
                {"anilist": 300, "similarity": 0.95},
            ],
        }
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(200, payload))

        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            result = await identify_via_tracemoe(b"img-bytes", min_similarity=0.88)

        self.assertIsNotNone(result)
        self.assertEqual(result.anilist_id, 300)
        self.assertAlmostEqual(result.similarity, 0.95)

    async def test_tracemoe_api_key_header_injected_only_when_set(self):
        payload = {"error": "", "result": [{"anilist": 16498, "similarity": 0.93}]}
        mock_cm, mock_client = _make_mock_httpx_client(response=_make_response(200, payload))

        with patch.dict(os.environ, {"TRACE_MOE_API_KEY": "  secret-trace-key  "}):
            with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
                result = await identify_via_tracemoe(b"img-bytes")

        self.assertIsNotNone(result)
        _, call_kwargs = mock_client.post.call_args
        self.assertEqual(call_kwargs["headers"]["x-trace-key"], "secret-trace-key")

    async def test_tracemoe_excludes_adult_entry_and_respects_exclude_adult_false(self):
        payload = {
            "error": "",
            "result": [
                {"anilist": {"id": 999, "isAdult": True}, "similarity": 0.96},
                {"anilist": {"id": 11061, "isAdult": False}, "similarity": 0.90},
            ],
        }
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(200, payload))
        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            filtered = await identify_via_tracemoe(b"img-bytes", min_similarity=0.88, exclude_adult=True)
        self.assertIsNotNone(filtered)
        self.assertEqual(filtered.anilist_id, 11061)

        mock_cm2, _ = _make_mock_httpx_client(response=_make_response(200, payload))
        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm2):
            unfiltered = await identify_via_tracemoe(b"img-bytes", min_similarity=0.88, exclude_adult=False)
        self.assertIsNotNone(unfiltered)
        self.assertEqual(unfiltered.anilist_id, 999)

    async def test_tracemoe_nan_min_similarity_falls_back_to_default_threshold(self):
        payload = {"error": "", "result": [{"anilist": 1, "similarity": 0.50}]}
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(200, payload))

        with patch("services.tracemoe_service.httpx.AsyncClient", return_value=mock_cm):
            result = await identify_via_tracemoe(b"img-bytes", min_similarity=float("nan"))

        self.assertIsNone(result)

    def test_tracemoe_env_helpers_and_to_dict(self):
        with patch.dict(os.environ, {"TRACE_MOE_ENABLED": "false"}):
            self.assertFalse(is_tracemoe_enabled())
        with patch.dict(os.environ, {"TRACE_MOE_ENABLED": "YES"}):
            self.assertTrue(is_tracemoe_enabled())

        with patch.dict(os.environ, {"TRACE_MOE_THRESHOLD": "0.91"}):
            self.assertAlmostEqual(get_tracemoe_threshold(), 0.91)
        with patch.dict(os.environ, {"TRACE_MOE_THRESHOLD": "not-a-float"}):
            self.assertEqual(get_tracemoe_threshold(), DEFAULT_TRACE_MOE_THRESHOLD)
        with patch.dict(os.environ, {"TRACE_MOE_THRESHOLD": "1.5"}):
            self.assertEqual(get_tracemoe_threshold(), DEFAULT_TRACE_MOE_THRESHOLD)
        with patch.dict(os.environ, {"TRACE_MOE_THRESHOLD": "0"}):
            self.assertEqual(get_tracemoe_threshold(), DEFAULT_TRACE_MOE_THRESHOLD)
        with patch.dict(os.environ, {"TRACE_MOE_THRESHOLD": "nan"}):
            self.assertEqual(get_tracemoe_threshold(), DEFAULT_TRACE_MOE_THRESHOLD)

        with patch.dict(os.environ, {"TRACE_MOE_API_KEY": "   "}):
            self.assertIsNone(get_tracemoe_api_key())

        dto = TraceMoeResult(
            anilist_id=154587,
            similarity=0.94,
            episode=1,
            from_sec=12.5,
            to_sec=14.0,
            filename="ep1.mp4",
            is_adult=False,
        )
        self.assertEqual(
            dto.to_dict(),
            {
                "anilistId": 154587,
                "similarity": 0.94,
                "episode": 1,
                "from": 12.5,
                "to": 14.0,
                "filename": "ep1.mp4",
                "isAdult": False,
            },
        )


class TestPhase2AniListById(unittest.IsolatedAsyncioTestCase):
    async def test_anilist_fetch_anime_info_by_id_success(self):
        mock_media = {
            "id": 154587,
            "title": {
                "romaji": "Sousou no Frieren",
                "english": "Frieren: Beyond Journey's End",
                "native": "葬送のフリーレン",
            },
        }
        mock_cm, mock_client = _make_mock_httpx_client(
            response=_make_response(200, {"data": {"Media": mock_media}})
        )

        with patch("services.anilist_service.httpx.AsyncClient", return_value=mock_cm):
            media = await fetch_anime_info_by_id(154587)

        self.assertEqual(media["id"], 154587)
        self.assertEqual(media["title"]["english"], "Frieren: Beyond Journey's End")
        _, call_kwargs = mock_client.post.call_args
        self.assertEqual(call_kwargs["json"]["variables"], {"id": 154587})
        self.assertIn("$id: Int", call_kwargs["json"]["query"])

    async def test_anilist_fetch_anime_info_by_title_preserved(self):
        mock_media = {"id": 9253, "title": {"romaji": "Steins;Gate", "english": "Steins;Gate"}}
        mock_cm, mock_client = _make_mock_httpx_client(
            response=_make_response(200, {"data": {"Media": mock_media}})
        )

        with patch("services.anilist_service.httpx.AsyncClient", return_value=mock_cm):
            media = await fetch_anime_info("Steins;Gate")

        self.assertEqual(media["id"], 9253)
        _, call_kwargs = mock_client.post.call_args
        self.assertEqual(call_kwargs["json"]["variables"], {"search": "Steins;Gate"})

    async def test_anilist_fetch_anime_info_by_id_invalid_id_raises(self):
        for bad_id in (0, -5, True, 1.5, "123"):
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(ValueError):
                    await fetch_anime_info_by_id(bad_id)  # type: ignore[arg-type]

    async def test_anilist_fetch_anime_info_by_id_error_paths(self):
        # 200 with Media: None
        mock_cm, _ = _make_mock_httpx_client(response=_make_response(200, {"data": {"Media": None}}))
        with patch("services.anilist_service.httpx.AsyncClient", return_value=mock_cm):
            with self.assertRaises(Exception) as ctx:
                await fetch_anime_info_by_id(99999999)
        self.assertIn("ID 99999999", str(ctx.exception))

        # HTTP 404 with AniList errors payload
        mock_cm_404, _ = _make_mock_httpx_client(
            response=_make_response(404, {"errors": [{"message": "Not Found."}]})
        )
        with patch("services.anilist_service.httpx.AsyncClient", return_value=mock_cm_404):
            with self.assertRaises(Exception) as ctx404:
                await fetch_anime_info_by_id(99999999)
        self.assertIn("Not Found.", str(ctx404.exception))

        # Network error
        mock_cm_err, _ = _make_mock_httpx_client(side_effect=httpx.ConnectError("unreachable"))
        with patch("services.anilist_service.httpx.AsyncClient", return_value=mock_cm_err):
            with self.assertRaises(Exception) as ctx_net:
                await fetch_anime_info_by_id(154587)
        self.assertIn("Failed to communicate with Anilist", str(ctx_net.exception))


if __name__ == "__main__":
    unittest.main()
