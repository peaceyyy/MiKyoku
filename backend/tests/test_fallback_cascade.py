"""
Integration tests for Phase 4: 3-tier fallback cascade (FAISS -> trace.moe -> Gemini)
and confidence-gated live auto-ingestion.
"""

import itertools
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routes import identify_poster
from services.gemini_service import IdentificationResult
from services.tracemoe_service import TraceMoeResult

_IP_COUNTER = itertools.count(1)


def _make_request() -> Request:
    n = next(_IP_COUNTER)
    ip = f"10.0.{(n // 250) % 250}.{(n % 250) + 1}"
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/identify",
            "headers": [],
            "client": (ip, 12345),
        }
    )


def _make_upload(filename: str = "scene.png", content_type: str = "image/png") -> MagicMock:
    upload = MagicMock()
    upload.filename = filename
    upload.content_type = content_type
    upload.read = AsyncMock(return_value=b"fake-image-bytes")
    return upload


class TestPhase4FallbackCascade(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._env_patcher = patch.dict(os.environ, {}, clear=False)
        self._env_patcher.start()
        for key in ("TRACE_MOE_ENABLED", "TRACE_MOE_THRESHOLD", "AUTO_INGEST_HIGH_CONFIDENCE"):
            os.environ.pop(key, None)

    def tearDown(self):
        self._env_patcher.stop()

    async def test_tier1_rag_hit_skips_tracemoe_and_gemini(self):
        media = {"id": 9253, "title": {"english": "Steins;Gate", "romaji": "Steins;Gate"}}
        with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "PNG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": True, "anime_title": "Steins;Gate", "similarity": 0.92, "top_matches": []})), \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock()) as mock_tm, \
             patch("api.routes.identify_via_gemini", new=AsyncMock()) as mock_gemini, \
             patch("api.routes.fetch_anime_info", new=AsyncMock(return_value=media)), \
             patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
            resp = await identify_poster(_make_request(), file=_make_upload(), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

        body = json.loads(resp.body.decode("utf-8"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["identificationMethod"], "rag")
        self.assertFalse(body["autoIngested"])
        self.assertTrue(body["canReportIncorrect"])
        self.assertNotIn("needsConfirmation", body)
        mock_tm.assert_not_awaited()
        mock_gemini.assert_not_awaited()

    async def test_force_rag_skips_tracemoe_and_gemini_and_returns_404(self):
        with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "PNG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "similarity": 0.40, "top_matches": [], "reason": "below threshold"})), \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock()) as mock_tm, \
             patch("api.routes.identify_via_gemini", new=AsyncMock()) as mock_gemini:
            resp = await identify_poster(_make_request(), file=_make_upload(), force_rag=True, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

        self.assertEqual(resp.status_code, 404)
        mock_tm.assert_not_awaited()
        mock_gemini.assert_not_awaited()

    async def test_tier2_tracemoe_high_confidence_and_boundary_auto_ingest_and_init_when_none(self):
        media = {"id": 154587, "title": {"english": "Frieren: Beyond Journey's End", "romaji": "Sousou no Frieren"}}

        for sim, store_obj, expect_init in ((0.90, None, True), (0.94, MagicMock(), False)):
            with self.subTest(similarity=sim, rag_store_is_none=store_obj is None):
                tm_hit = TraceMoeResult(anilist_id=154587, similarity=sim, episode=1)
                with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "PNG"})), \
                     patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": [], "reason": "miss"})), \
                     patch("api.routes.identify_via_tracemoe", new=AsyncMock(return_value=tm_hit)), \
                     patch("api.routes.fetch_anime_info_by_id", new=AsyncMock(return_value=media)) as mock_by_id, \
                     patch("api.routes.identify_via_gemini", new=AsyncMock()) as mock_gemini, \
                     patch("api.routes.ingest_poster", new=AsyncMock(return_value={"success": True, "slug": "frieren_beyond_journey_s_end"})) as mock_ingest, \
                     patch("api.routes.initialize_rag") as mock_init_rag, \
                     patch("api.routes.rag_store", new=store_obj), \
                     patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
                    resp = await identify_poster(_make_request(), file=_make_upload("frame.png"), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

                body = json.loads(resp.body.decode("utf-8"))
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(body["identificationMethod"], "tracemoe")
                self.assertEqual(body["identifiedTitle"], "Frieren: Beyond Journey's End")
                self.assertTrue(body["autoIngested"])
                self.assertTrue(body["canReportIncorrect"])
                self.assertNotIn("needsConfirmation", body)
                mock_by_id.assert_awaited_once_with(154587)
                mock_gemini.assert_not_awaited()
                mock_ingest.assert_awaited_once()
                self.assertEqual(mock_ingest.call_args.kwargs["source"], "tracemoe")
                self.assertEqual(mock_ingest.call_args.kwargs["file_extension"], ".png")
                if expect_init:
                    mock_init_rag.assert_called_once()
                else:
                    mock_init_rag.assert_not_called()

    async def test_tier2_tracemoe_medium_confidence_requests_confirmation_without_auto_ingest(self):
        tm_hit = TraceMoeResult(anilist_id=154587, similarity=0.89, episode=2)
        media = {"id": 154587, "title": {"english": "Frieren: Beyond Journey's End"}}

        with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "PNG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": []})), \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock(return_value=tm_hit)), \
             patch("api.routes.fetch_anime_info_by_id", new=AsyncMock(return_value=media)), \
             patch("api.routes.ingest_poster", new=AsyncMock()) as mock_ingest, \
             patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
            resp = await identify_poster(_make_request(), file=_make_upload(), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

        body = json.loads(resp.body.decode("utf-8"))
        self.assertEqual(body["identificationMethod"], "tracemoe")
        self.assertFalse(body["autoIngested"])
        self.assertTrue(body["needsConfirmation"])
        mock_ingest.assert_not_awaited()

    async def test_tier2_tracemoe_respects_auto_ingest_disabled_and_tracemoe_disabled_env(self):
        tm_hit = TraceMoeResult(anilist_id=154587, similarity=0.96, episode=1)
        media = {"id": 154587, "title": {"english": "Frieren: Beyond Journey's End"}}

        with patch.dict(os.environ, {"AUTO_INGEST_HIGH_CONFIDENCE": "false"}), \
             patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "PNG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": []})), \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock(return_value=tm_hit)), \
             patch("api.routes.fetch_anime_info_by_id", new=AsyncMock(return_value=media)), \
             patch("api.routes.ingest_poster", new=AsyncMock()) as mock_ingest, \
             patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
            resp = await identify_poster(_make_request(), file=_make_upload(), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

        body = json.loads(resp.body.decode("utf-8"))
        self.assertEqual(body["identificationMethod"], "tracemoe")
        self.assertFalse(body["autoIngested"])
        self.assertTrue(body["needsConfirmation"])
        mock_ingest.assert_not_awaited()

        gemini_res = IdentificationResult(title="Frieren", is_anime=True, confidence="High")
        with patch.dict(os.environ, {"TRACE_MOE_ENABLED": "false"}), \
             patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "PNG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": []})), \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock()) as mock_tm, \
             patch("api.routes.gemini_is_configured", return_value=True), \
             patch("api.routes.identify_via_gemini", new=AsyncMock(return_value=gemini_res)), \
             patch("api.routes.resolve_anilist_from_candidates", new=AsyncMock(return_value=media)), \
             patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
            resp2 = await identify_poster(_make_request(), file=_make_upload(), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

        body2 = json.loads(resp2.body.decode("utf-8"))
        self.assertEqual(body2["identificationMethod"], "gemini")
        mock_tm.assert_not_awaited()

    async def test_tier2_miss_falls_through_to_tier3_gemini_and_503_when_unconfigured(self):
        gemini_res = IdentificationResult(title="Vinland Saga", is_anime=True, confidence="High", alt_titles=["ヴィンランド・サガ"])
        media = {"id": 101348, "title": {"english": "Vinland Saga", "romaji": "Vinland Saga"}}

        with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "JPEG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": []})), \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock(return_value=None)) as mock_tm, \
             patch("api.routes.gemini_is_configured", return_value=True), \
             patch("api.routes.identify_via_gemini", new=AsyncMock(return_value=gemini_res)) as mock_gemini, \
             patch("api.routes.resolve_anilist_from_candidates", new=AsyncMock(return_value=media)), \
             patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
            resp = await identify_poster(_make_request(), file=_make_upload("poster.jpg", "image/jpeg"), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

        body = json.loads(resp.body.decode("utf-8"))
        self.assertEqual(body["identificationMethod"], "gemini")
        self.assertEqual(body["identifiedTitle"], "Vinland Saga")
        self.assertFalse(body["autoIngested"])
        self.assertTrue(body["needsConfirmation"])
        mock_tm.assert_awaited_once()
        mock_gemini.assert_awaited_once()

        # Unconfigured Gemini raises 503 cleanly
        with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "JPEG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": []})), \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock(return_value=None)), \
             patch("api.routes.gemini_is_configured", return_value=False):
            with self.assertRaises(HTTPException) as ctx:
                await identify_poster(_make_request(), file=_make_upload("poster.jpg", "image/jpeg"), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)
        self.assertEqual(ctx.exception.status_code, 503)

    async def test_skip_rag_and_skip_tracemoe_flags_bypass_tiers_directly_to_gemini(self):
        gemini_res = IdentificationResult(title="Cowboy Bebop", is_anime=True, confidence="High")
        media = {"id": 1, "title": {"english": "Cowboy Bebop"}}

        with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "JPEG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock()) as mock_rag, \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock()) as mock_tm, \
             patch("api.routes.gemini_is_configured", return_value=True), \
             patch("api.routes.identify_via_gemini", new=AsyncMock(return_value=gemini_res)) as mock_gemini, \
             patch("api.routes.resolve_anilist_from_candidates", new=AsyncMock(return_value=media)), \
             patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
            resp = await identify_poster(_make_request(), file=_make_upload("poster.jpg", "image/jpeg"), force_rag=False, similarity_threshold=0.70, skip_tracemoe=True, skip_rag=True)

        body = json.loads(resp.body.decode("utf-8"))
        self.assertEqual(body["identificationMethod"], "gemini")
        mock_rag.assert_not_awaited()
        mock_tm.assert_not_awaited()
        mock_gemini.assert_awaited_once()

    async def test_tier2_anilist_404_falls_through_but_outage_raises_503(self):
        tm_hit = TraceMoeResult(anilist_id=99999999, similarity=0.95)
        gemini_res = IdentificationResult(title="Mob Psycho 100", is_anime=True, confidence="High")
        media = {"id": 21507, "title": {"english": "Mob Psycho 100"}}

        for not_found_msg in (
            "No results found for ID 99999999.",
            "No results found for ID 99999999. (Not Found.)",
        ):
            with self.subTest(not_found_msg=not_found_msg):
                with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "JPEG"})), \
                     patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": []})), \
                     patch("api.routes.identify_via_tracemoe", new=AsyncMock(return_value=tm_hit)), \
                     patch("api.routes.fetch_anime_info_by_id", new=AsyncMock(side_effect=Exception(not_found_msg))), \
                     patch("api.routes.gemini_is_configured", return_value=True), \
                     patch("api.routes.identify_via_gemini", new=AsyncMock(return_value=gemini_res)) as mock_gemini, \
                     patch("api.routes.resolve_anilist_from_candidates", new=AsyncMock(return_value=media)), \
                     patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
                    resp = await identify_poster(_make_request(), file=_make_upload("poster.jpg", "image/jpeg"), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

                body = json.loads(resp.body.decode("utf-8"))
                self.assertEqual(body["identificationMethod"], "gemini")
                self.assertEqual(body["identifiedTitle"], "Mob Psycho 100")
                mock_gemini.assert_awaited_once()

        # Real AniList outage (503/network) must NOT fall through to Gemini and returns 503
        with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "JPEG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": []})), \
             patch("api.routes.identify_via_tracemoe", new=AsyncMock(return_value=tm_hit)), \
             patch("api.routes.fetch_anime_info_by_id", new=AsyncMock(side_effect=Exception("Could not connect to anime database. (Status: 503)"))), \
             patch("api.routes.identify_via_gemini", new=AsyncMock()) as mock_gemini:
            with self.assertRaises(HTTPException) as ctx:
                await identify_poster(_make_request(), file=_make_upload("poster.jpg", "image/jpeg"), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)
        self.assertEqual(ctx.exception.status_code, 503)
        mock_gemini.assert_not_awaited()

    async def test_auto_ingest_failures_are_non_fatal_and_fall_back_to_confirmation(self):
        tm_hit = TraceMoeResult(anilist_id=154587, similarity=0.95)
        media = {"id": 154587, "title": {"english": "Frieren: Beyond Journey's End"}}

        for ingest_mock in (
            AsyncMock(side_effect=RuntimeError("disk I/O error")),
            AsyncMock(return_value={"success": False, "error": "lock timeout"}),
        ):
            with self.subTest(ingest_mock=ingest_mock):
                with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "PNG"})), \
                     patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "top_matches": []})), \
                     patch("api.routes.identify_via_tracemoe", new=AsyncMock(return_value=tm_hit)), \
                     patch("api.routes.fetch_anime_info_by_id", new=AsyncMock(return_value=media)), \
                     patch("api.routes.ingest_poster", new=ingest_mock), \
                     patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
                    resp = await identify_poster(_make_request(), file=_make_upload(), force_rag=False, similarity_threshold=0.70, skip_tracemoe=False, skip_rag=False)

                body = json.loads(resp.body.decode("utf-8"))
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(body["identificationMethod"], "tracemoe")
                self.assertFalse(body["autoIngested"])
                self.assertTrue(body["needsConfirmation"])


if __name__ == "__main__":
    unittest.main()
