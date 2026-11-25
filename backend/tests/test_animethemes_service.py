"""
Unit tests for AnimeThemes Rust GraphQL service (rs.animethemes.moe/graphql).
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.animethemes_service import (
    ANIMETHEMES_GRAPHQL_URL,
    fetch_themes_from_api,
)


def _mock_response(status_code: int, payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = payload
    return resp


class TestAnimeThemesGraphQLService(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_by_anilist_id_maps_op_ed_in_artists_and_video_link(self):
        gql_payload = {
            "data": {
                "filterAnimeByExternalSite": [
                    {
                        "title": {
                            "romaji": "Wonder Egg Priority",
                            "english": "WONDER EGG PRIORITY",
                            "native": "ワンダーエッグ・プライオリティ",
                        },
                        "themes": [
                            {
                                "type": "OP",
                                "sequence": 1,
                                "song": {
                                    "title": {"romaji": "Sudachi no Uta"},
                                    "staff": [
                                        {
                                            "alias": None,
                                            "role": "Vocals",
                                            "artist": {"name": {"main": "Anemoneria"}},
                                        },
                                        {
                                            "alias": None,
                                            "role": "Vocals",
                                            "artist": {"name": {"main": "anemoneria"}},
                                        },
                                    ],
                                },
                                "entries": [
                                    {
                                        "videos": {
                                            "nodes": [
                                                {
                                                    "basename": "WonderEggPriority-OP1-NCBD1080.webm",
                                                    "link": "https://v.animethemes.moe/WonderEggPriority-OP1-NCBD1080.webm",
                                                }
                                            ]
                                        }
                                    }
                                ],
                            },
                            {
                                "type": "ED",
                                "sequence": 1,
                                "song": {
                                    "title": {"romaji": "Life is Cider"},
                                    "staff": [
                                        {
                                            "alias": "Anemoneria (Alias)",
                                            "role": "Vocals",
                                            "artist": {"name": {"main": "Anemoneria"}},
                                        }
                                    ],
                                },
                                "entries": [
                                    {
                                        "videos": {
                                            "nodes": [
                                                {
                                                    "basename": "WonderEggPriority-ED1.webm",
                                                    "link": "",
                                                }
                                            ]
                                        }
                                    }
                                ],
                            },
                            {
                                "type": "IN",
                                "sequence": 1,
                                "song": {"title": {"romaji": "Insert Track"}, "staff": []},
                                "entries": [],
                            },
                        ],
                    }
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, gql_payload))
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_client

        with patch("services.animethemes_service.httpx.AsyncClient", return_value=mock_cm):
            collections = await fetch_themes_from_api("WONDER EGG PRIORITY", anilist_id=124845)

        self.assertEqual(len(collections), 1)
        col = collections[0]
        self.assertEqual(col["seasonName"], "Wonder Egg Priority")
        self.assertEqual(len(col["openings"]), 1)
        self.assertEqual(col["openings"][0]["title"], "Sudachi no Uta")
        self.assertEqual(col["openings"][0]["artist"], "Anemoneria")
        self.assertEqual(
            col["openings"][0]["videoUrl"],
            "https://v.animethemes.moe/WonderEggPriority-OP1-NCBD1080.webm",
        )
        self.assertEqual(col["endings"][0]["artist"], "Anemoneria (Alias)")
        self.assertEqual(
            col["endings"][0]["videoUrl"],
            "https://v.animethemes.moe/WonderEggPriority-ED1.webm",
        )
        self.assertEqual(col["osts"][0]["title"], "Insert Track")
        self.assertEqual(col["osts"][0]["artist"], "Unknown Artist")
        self.assertIsNone(col["osts"][0]["videoUrl"])

        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args.args[0], ANIMETHEMES_GRAPHQL_URL)
        self.assertEqual(call_args.kwargs["json"]["variables"], {"id": [124845]})

    async def test_falls_back_to_title_search_when_anilist_id_empty(self):
        empty_id_resp = _mock_response(200, {"data": {"filterAnimeByExternalSite": []}})
        search_resp = _mock_response(
            200,
            {
                "data": {
                    "search": {
                        "anime": {
                            "data": [
                                {
                                    "title": {"romaji": "Unrelated Show", "english": None, "native": None},
                                    "themes": [
                                        {
                                            "type": "OP",
                                            "song": {"title": {"romaji": "Wrong"}, "staff": []},
                                            "entries": [],
                                        }
                                    ],
                                },
                                {
                                    "title": {
                                        "romaji": "Sousou no Frieren",
                                        "english": "Frieren: Beyond Journey's End",
                                        "native": "葬送のフリーレン",
                                    },
                                    "themes": [
                                        {
                                            "type": "OP",
                                            "song": {
                                                "title": {"romaji": "Yuusha"},
                                                "staff": [{"artist": {"name": {"main": "YOASOBI"}}}],
                                            },
                                            "entries": [],
                                        }
                                    ],
                                },
                            ]
                        }
                    }
                }
            },
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[empty_id_resp, search_resp])
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_client

        with patch("services.animethemes_service.httpx.AsyncClient", return_value=mock_cm):
            collections = await fetch_themes_from_api("Frieren: Beyond Journey's End", anilist_id=999999)

        self.assertEqual(len(collections), 1)
        self.assertEqual(collections[0]["seasonName"], "Sousou no Frieren")
        self.assertEqual(collections[0]["openings"][0]["title"], "Yuusha")
        self.assertEqual(collections[0]["openings"][0]["artist"], "YOASOBI")

    async def test_retries_once_on_503_then_succeeds(self):
        resp_503 = _mock_response(503, {})
        resp_200 = _mock_response(
            200,
            {
                "data": {
                    "search": {
                        "anime": {
                            "data": [
                                {
                                    "title": {"romaji": "Steins;Gate", "english": "Steins;Gate", "native": None},
                                    "themes": [
                                        {
                                            "type": "OP",
                                            "song": {
                                                "title": {"romaji": "Hacking to the Gate"},
                                                "staff": [{"artist": {"name": {"main": "Kanako Itou"}}}],
                                            },
                                            "entries": [],
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                }
            },
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[resp_503, resp_200])
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_client

        with patch("services.animethemes_service.httpx.AsyncClient", return_value=mock_cm), \
             patch("services.animethemes_service.asyncio.sleep", new=AsyncMock()):
            collections = await fetch_themes_from_api("Steins;Gate")

        self.assertEqual(len(collections), 1)
        self.assertEqual(collections[0]["openings"][0]["title"], "Hacking to the Gate")
        self.assertEqual(mock_client.post.await_count, 2)

    async def test_graphql_error_returns_empty_list(self):
        err_resp = _mock_response(200, {"data": None, "errors": [{"message": "Bad query"}]})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=err_resp)
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_client

        with patch("services.animethemes_service.httpx.AsyncClient", return_value=mock_cm):
            collections = await fetch_themes_from_api("Wonder Egg Priority", anilist_id=124845)

        self.assertEqual(collections, [])


if __name__ == "__main__":
    unittest.main()
