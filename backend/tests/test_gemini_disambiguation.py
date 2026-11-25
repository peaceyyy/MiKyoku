"""
Unit tests for Phase 3: Configurable GEMINI_MODEL, OCR/Multi-Candidate Prompt,
and AniList Disambiguation.
"""

import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import services.gemini_service as gemini_service
from api.routes import (
    _pick_best_anilist_match,
    identify_poster,
    identify_via_gemini,
    resolve_anilist_from_candidates,
)
from services.gemini_service import (
    DEFAULT_GEMINI_MODEL,
    IdentificationResult,
    fetch_supplemental_themes,
    find_youtube_video_id,
    get_client,
    get_gemini_model,
    identify_anime_from_poster,
    is_configured,
)


class TestPhase3GeminiService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._env_patcher = patch.dict(os.environ, {}, clear=False)
        self._env_patcher.start()
        os.environ.pop("GEMINI_MODEL", None)
        os.environ["GEMINI_API_KEY"] = "test-gemini-key"
        gemini_service._client = None
        gemini_service._client_api_key = None

    def tearDown(self):
        self._env_patcher.stop()
        gemini_service._client = None
        gemini_service._client_api_key = None

    def test_get_gemini_model_default_override_and_blank_fallback(self):
        self.assertEqual(get_gemini_model(), DEFAULT_GEMINI_MODEL)

        with patch.dict(os.environ, {"GEMINI_MODEL": "  gemini-3.5-flash  "}):
            self.assertEqual(get_gemini_model(), "gemini-3.5-flash")

        with patch.dict(os.environ, {"GEMINI_MODEL": "   "}):
            self.assertEqual(get_gemini_model(), DEFAULT_GEMINI_MODEL)

    def test_client_config_and_key_rotation(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with patch.object(gemini_service, "GEMINI_API_KEY", None):
                self.assertFalse(is_configured())
                with self.assertRaises(gemini_service.GeminiNotConfiguredError):
                    get_client()

        with patch("services.gemini_service.genai.Client") as mock_client_cls:
            mock_client_cls.side_effect = ["client-1", "client-2"]
            with patch.dict(os.environ, {"GEMINI_API_KEY": "key-1"}):
                c1 = get_client()
                c1_again = get_client()
            with patch.dict(os.environ, {"GEMINI_API_KEY": "key-2"}):
                c2 = get_client()

        self.assertEqual(c1, "client-1")
        self.assertEqual(c1_again, "client-1")
        self.assertEqual(c2, "client-2")
        self.assertEqual(mock_client_cls.call_count, 2)

    def test_identification_result_direct_normalization(self):
        res_high = IdentificationResult("Show", is_anime=True, confidence=" high ")
        self.assertEqual(res_high.confidence, "High")

        res_non_anime = IdentificationResult(
            "A car",
            is_anime=False,
            confidence="invalid",
            alt_titles=["Sports Car"],
            ocr_text="  ",
        )
        self.assertEqual(res_non_anime.confidence, "Medium")
        self.assertEqual(res_non_anime.alt_titles, [])
        self.assertIsNone(res_non_anime.ocr_text)

    async def test_identify_anime_from_poster_uses_configured_model_and_parses_candidates(self):
        payload = {
            "title": "Frieren: Beyond Journey's End",
            "altTitles": ["Sousou no Frieren", "葬送のフリーレン", "Frieren"],
            "ocrText": "葬送のフリーレン",
            "isAnime": True,
            "confidence": "High",
        }
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(
            return_value=SimpleNamespace(text=json.dumps(payload))
        )

        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-4-flash-preview"}):
            with patch("services.gemini_service.get_client", return_value=mock_client):
                result = await identify_anime_from_poster("ZmFrZQ==", "image/jpeg")

        mock_client.models.generate_content.assert_called_once()
        _, call_kwargs = mock_client.models.generate_content.call_args
        self.assertEqual(call_kwargs["model"], "gemini-4-flash-preview")
        self.assertEqual(call_kwargs["config"].response_mime_type, "application/json")
        self.assertEqual(len(call_kwargs["contents"]), 2)
        self.assertTrue(result.is_anime)
        self.assertEqual(result.title, "Frieren: Beyond Journey's End")
        self.assertEqual(result.confidence, "High")
        self.assertEqual(result.alt_titles, ["Sousou no Frieren", "葬送のフリーレン", "Frieren"])
        self.assertEqual(result.ocr_text, "葬送のフリーレン")

    async def test_identify_anime_from_poster_strips_markdown_fences_and_dedupes_alt_titles(self):
        fenced_json = """```json
        {
          "title": "Steins;Gate",
          "altTitles": ["steins;gate", "STEINS;GATE", "シュタインズ・ゲート", "  ", "Steins Gate", "Extra Third", "Dropped Fourth"],
          "ocrText": "  STEINS;GATE  ",
          "isAnime": "true",
          "confidence": "high"
        }
        ```"""
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(
            return_value=SimpleNamespace(text=fenced_json)
        )

        with patch("services.gemini_service.get_client", return_value=mock_client):
            result = await identify_anime_from_poster("ZmFrZQ==", "image/png")

        self.assertTrue(result.is_anime)
        self.assertEqual(result.title, "Steins;Gate")
        self.assertEqual(result.confidence, "High")
        self.assertEqual(result.alt_titles, ["シュタインズ・ゲート", "Steins Gate", "Extra Third"])
        self.assertEqual(result.ocr_text, "STEINS;GATE")

    async def test_identify_anime_from_poster_error_and_non_anime_handling(self):
        payload = {
            "title": "Photograph of a red sports car",
            "altTitles": ["Sports Car"],
            "ocrText": None,
            "isAnime": False,
            "confidence": "High",
        }
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(
            return_value=SimpleNamespace(text=json.dumps(payload))
        )
        with patch("services.gemini_service.get_client", return_value=mock_client):
            result = await identify_anime_from_poster("ZmFrZQ==", "image/jpeg")
        self.assertFalse(result.is_anime)
        self.assertEqual(result.alt_titles, [])
        self.assertIsNone(result.ocr_text)

        # Unrelated RuntimeError should NOT be reported as missing GEMINI_API_KEY
        mock_client.models.generate_content = MagicMock(side_effect=RuntimeError("SDK transport failure"))
        with patch("services.gemini_service.get_client", return_value=mock_client):
            with self.assertRaises(Exception) as ctx:
                await identify_anime_from_poster("ZmFrZQ==", "image/jpeg")
        self.assertIn("SDK transport failure", str(ctx.exception))
        self.assertNotIn("GEMINI_API_KEY", str(ctx.exception))

        # Non-dict JSON fails cleanly
        mock_client.models.generate_content = MagicMock(return_value=SimpleNamespace(text="[]"))
        with patch("services.gemini_service.get_client", return_value=mock_client):
            with self.assertRaises(Exception) as ctx2:
                await identify_anime_from_poster("ZmFrZQ==", "image/jpeg")
        self.assertIn("Failed to identify the image", str(ctx2.exception))

    async def test_supplemental_themes_and_youtube_fallback_use_configured_model(self):
        themes_payload = [
            {
                "seasonName": "Season 1",
                "openings": [{"title": "Yuusha", "artist": "YOASOBI"}],
                "endings": [],
                "osts": [{"title": "Zoltraak", "artist": "Evan Call"}],
            }
        ]
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(
            side_effect=[
                SimpleNamespace(text=json.dumps(themes_payload)),
                SimpleNamespace(text="dQw4w9WgXcQ"),
            ]
        )

        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-custom-test"}):
            with patch("services.gemini_service.get_client", return_value=mock_client):
                seasons = await fetch_supplemental_themes("Frieren")
                with patch(
                    "services.youtube_service.search_youtube_video_id",
                    new=AsyncMock(return_value=None),
                ):
                    video_id = await find_youtube_video_id("Yuusha YOASOBI")

        self.assertEqual(len(seasons), 1)
        self.assertEqual(seasons[0].openings[0].title, "Yuusha")
        self.assertEqual(video_id, "dQw4w9WgXcQ")
        self.assertEqual(mock_client.models.generate_content.call_count, 2)
        for call in mock_client.models.generate_content.call_args_list:
            self.assertEqual(call.kwargs["model"], "gemini-custom-test")


class TestPhase3AniListDisambiguation(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_anilist_primary_hit_skips_search_anime(self):
        primary_media = {"id": 154587, "title": {"english": "Frieren: Beyond Journey's End"}}
        with patch("api.routes.fetch_anime_info", new=AsyncMock(return_value=primary_media)) as mock_fetch, \
             patch("api.routes.search_anime", new=AsyncMock()) as mock_search:
            media = await resolve_anilist_from_candidates(
                "Frieren: Beyond Journey's End",
                alt_titles=["Sousou no Frieren"],
                ocr_text="葬送のフリーレン",
            )

        self.assertEqual(media["id"], 154587)
        mock_fetch.assert_awaited_once_with("Frieren: Beyond Journey's End")
        mock_search.assert_not_awaited()

    async def test_resolve_anilist_falls_back_to_alt_title_and_prefers_candidate_priority(self):
        ocr_match = {"id": 2, "title": {"english": "Other", "romaji": "Other", "native": "OCR_ONLY"}}
        alt_match = {"id": 9253, "title": {"english": None, "romaji": "Steins;Gate", "native": None}}

        with patch("api.routes.fetch_anime_info", new=AsyncMock(side_effect=Exception('No results found for "Steins Gate Movie?".'))), \
             patch("api.routes.search_anime", new=AsyncMock(return_value={"results": [ocr_match, alt_match]})) as mock_search:
            media = await resolve_anilist_from_candidates(
                "Steins Gate Movie?",
                alt_titles=["Steins;Gate"],
                ocr_text="OCR_ONLY",
            )

        self.assertEqual(media["id"], 9253)
        mock_search.assert_awaited_once_with("Steins;Gate", page=1, per_page=5)

    def test_pick_best_anilist_match_falls_back_to_first_dict(self):
        first = {"id": 42, "title": {"english": "First Result"}}
        second = {"id": 43, "title": {"english": "Second Result"}}
        self.assertEqual(_pick_best_anilist_match([None, first, second], ["Unmatched"])["id"], 42)  # type: ignore[list-item]

    async def test_resolve_anilist_falls_back_to_ocr_text_and_handles_unknown_primary(self):
        ocr_media = {"id": 101922, "title": {"english": "Demon Slayer", "romaji": "Kimetsu no Yaiba", "native": "鬼滅の刃"}}

        async def _search_side_effect(query, page=1, per_page=5):
            if query == "鬼滅の刃":
                return {"results": [ocr_media]}
            return {"results": []}

        with patch("api.routes.fetch_anime_info", new=AsyncMock()) as mock_fetch, \
             patch("api.routes.search_anime", new=AsyncMock(side_effect=_search_side_effect)) as mock_search:
            media = await resolve_anilist_from_candidates(
                "Unknown",
                alt_titles=["Bad Candidate"],
                ocr_text="鬼滅の刃",
            )

        self.assertEqual(media["id"], 101922)
        mock_fetch.assert_not_awaited()
        self.assertEqual(mock_search.await_count, 2)

    async def test_resolve_anilist_short_circuits_on_outage_in_primary_or_fallback(self):
        for outage_msg in (
            "Failed to communicate with Anilist.",
            "Could not connect to anime database. (Status: 503)",
        ):
            with self.subTest(outage_msg=outage_msg):
                with patch("api.routes.fetch_anime_info", new=AsyncMock(side_effect=Exception(outage_msg))) as mock_fetch, \
                     patch("api.routes.search_anime", new=AsyncMock()) as mock_search:
                    with self.assertRaises(Exception) as ctx:
                        await resolve_anilist_from_candidates("Frieren", alt_titles=["Sousou no Frieren"])
                self.assertIn(outage_msg, str(ctx.exception))
                mock_fetch.assert_awaited_once()
                mock_search.assert_not_awaited()

        # Outage during fallback search_anime must propagate instead of being masked by primary_err
        with patch("api.routes.fetch_anime_info", new=AsyncMock(side_effect=Exception('No results found for "Bad".'))), \
             patch("api.routes.search_anime", new=AsyncMock(side_effect=Exception("Could not search anime database. (Status: 429)"))) as mock_search:
            with self.assertRaises(Exception) as ctx2:
                await resolve_anilist_from_candidates("Bad", alt_titles=["Alt 1", "Alt 2"])
        self.assertIn("429", str(ctx2.exception))
        mock_search.assert_awaited_once()

    async def test_resolve_anilist_raises_primary_error_when_all_candidates_fail(self):
        with patch("api.routes.fetch_anime_info", new=AsyncMock(side_effect=Exception('No results found for "Unknown Show".'))), \
             patch("api.routes.search_anime", new=AsyncMock(return_value={"results": []})):
            with self.assertRaises(Exception) as ctx:
                await resolve_anilist_from_candidates(
                    "Unknown Show",
                    alt_titles=["Alt 1"],
                    ocr_text="不明",
                )

        self.assertIn("Unknown Show", str(ctx.exception))

    async def test_identify_via_gemini_returns_full_result_and_rejects_non_anime(self):
        anime_res = IdentificationResult(
            title="Vinland Saga",
            is_anime=True,
            confidence="High",
            alt_titles=["ヴィンランド・サガ"],
            ocr_text="VINLAND SAGA",
        )
        with patch("api.routes.identify_anime_from_poster", new=AsyncMock(return_value=anime_res)):
            res = await identify_via_gemini(b"fake-bytes", "image/jpeg")
        self.assertIsInstance(res, IdentificationResult)
        self.assertEqual(res.title, "Vinland Saga")
        self.assertEqual(res.alt_titles, ["ヴィンランド・サガ"])

        non_anime_res = IdentificationResult(title="A cat", is_anime=False, confidence="High")
        with patch("api.routes.identify_anime_from_poster", new=AsyncMock(return_value=non_anime_res)):
            with self.assertRaises(HTTPException) as ctx:
                await identify_via_gemini(b"fake-bytes", "image/jpeg")
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_identify_poster_uses_validated_title_after_disambiguation(self):
        fake_upload = MagicMock()
        fake_upload.filename = "poster.jpg"
        fake_upload.content_type = "image/jpeg"
        fake_upload.read = AsyncMock(return_value=b"fake-jpg-bytes")

        fake_request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/identify",
                "headers": [],
                "client": ("127.0.0.1", 12345),
            }
        )

        gemini_res = IdentificationResult(
            title="Wrong Raw Guess",
            is_anime=True,
            confidence="Medium",
            alt_titles=["Steins;Gate"],
            ocr_text="STEINS;GATE",
        )
        resolved_media = {
            "id": 9253,
            "title": {"english": "Steins;Gate", "romaji": "Steins;Gate", "native": "シュタインズ・ゲート"},
        }

        with patch("api.routes.validate_image", return_value=(True, None, {"width": 100, "height": 100, "format": "JPEG"})), \
             patch("api.routes.identify_via_rag", new=AsyncMock(return_value={"found": False, "reason": "miss", "top_matches": []})), \
             patch("api.routes.gemini_is_configured", return_value=True), \
             patch("api.routes.identify_via_gemini", new=AsyncMock(return_value=gemini_res)), \
             patch("api.routes.resolve_anilist_from_candidates", new=AsyncMock(return_value=resolved_media)), \
             patch("api.routes.fetch_themes_in_parallel", new=AsyncMock(return_value=([], []))):
            resp = await identify_poster(
                fake_request,
                file=fake_upload,
                force_rag=False,
                similarity_threshold=0.70,
                skip_tracemoe=True,
            )

        body = json.loads(resp.body.decode("utf-8"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["identificationMethod"], "gemini")
        self.assertEqual(body["identifiedTitle"], "Steins;Gate")
        self.assertEqual(body["ragDebug"]["raw_gemini_title"], "Wrong Raw Guess")
        self.assertEqual(body["ragDebug"]["alt_titles"], ["Steins;Gate"])
        self.assertEqual(body["ragDebug"]["ocr_text"], "STEINS;GATE")


if __name__ == "__main__":
    unittest.main()
