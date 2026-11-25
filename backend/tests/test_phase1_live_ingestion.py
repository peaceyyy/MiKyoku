"""
Unit tests for Phase 1: Live FAISS Write-Through and DATA_DIR_PATH Resolution.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.ingestion import _is_same_anime_slug, get_data_dir, ingest_poster
from rag.vector_store import VectorStore


def _make_unit_vector(seed: int, dim: int = 512) -> np.ndarray:
    """Create a deterministic L2-normalized 512-dim float32 vector."""
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=dim).astype("float32")
    vec /= np.linalg.norm(vec)
    return vec


class TestPhase1LiveIngestion(unittest.IsolatedAsyncioTestCase):
    async def test_live_vector_store_updated_without_reload(self):
        vec = _make_unit_vector(101)
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            store = VectorStore(
                index_path=str(data_dir / "index.faiss"),
                metadata_path=str(data_dir / "posters.json"),
                dimension=512,
            )
            self.assertEqual(store.index.ntotal, 0)

            with patch("rag.ingestion.generate_embedding", new=AsyncMock(return_value=vec)):
                result = await ingest_poster(
                    image_bytes=b"fake-image-bytes",
                    anime_title="Frieren: Beyond Journey's End",
                    source="gemini",
                    save_image=True,
                    file_extension=".jpg",
                    vector_store=store,
                    data_dir=data_dir,
                )

            self.assertTrue(result["success"])
            self.assertFalse(result["skipped_duplicate"])
            self.assertEqual(result["index_id"], 0)
            self.assertEqual(result["index_size"], 1)
            self.assertEqual(result["poster_path"], f"data/posters/{result['slug']}.jpg")

            # Live in-memory store assertions
            self.assertEqual(store.index.ntotal, 1)
            self.assertEqual(store.id_to_slug, [result["slug"]])
            self.assertIn(result["slug"], store.metadata)
            stats = store.get_stats()
            self.assertEqual(stats["total_vectors"], 1)
            self.assertEqual(stats["metadata_count"], 1)
            self.assertEqual(stats["mapped_ids"], 1)

            saved_img = data_dir / "posters" / f"{result['slug']}.jpg"
            self.assertTrue(saved_img.exists())
            self.assertEqual(saved_img.read_bytes(), b"fake-image-bytes")

            matches = store.search(vec, k=1)
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].slug, result["slug"])
            self.assertEqual(matches[0].anime_title, "Frieren: Beyond Journey's End")
            self.assertGreaterEqual(matches[0].similarity, 0.99)

    async def test_data_dir_path_env_var_respected_and_empty_string_fallback(self):
        vec = _make_unit_vector(202)
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            with patch.dict(os.environ, {"DATA_DIR_PATH": str(data_dir)}):
                self.assertEqual(get_data_dir(), data_dir)
                with patch("rag.ingestion.generate_embedding", new=AsyncMock(return_value=vec)):
                    result = await ingest_poster(
                        image_bytes=b"fake-image-bytes",
                        anime_title="Steins;Gate",
                        source="gemini",
                        save_image=True,
                        file_extension=".jpg",
                    )

            self.assertTrue(result["success"])
            self.assertTrue((data_dir / "index.faiss").exists())
            self.assertTrue((data_dir / "index.mapping.json").exists())
            self.assertTrue((data_dir / "posters.json").exists())
            self.assertTrue((data_dir / "posters" / f"{result['slug']}.jpg").exists())

            metadata = json.loads((data_dir / "posters.json").read_text(encoding="utf-8"))
            self.assertIn(result["slug"], metadata)

        with patch.dict(os.environ, {"DATA_DIR_PATH": ""}):
            self.assertEqual(get_data_dir().name, "data")

    async def test_near_duplicate_guard_skips_redundant_vector_and_handles_save_image_false(self):
        vec = _make_unit_vector(303)
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            store = VectorStore(
                index_path=str(data_dir / "index.faiss"),
                metadata_path=str(data_dir / "posters.json"),
                dimension=512,
            )

            with patch("rag.ingestion.generate_embedding", new=AsyncMock(return_value=vec)):
                first = await ingest_poster(
                    image_bytes=b"fake-image-1",
                    anime_title="Attack on Titan",
                    source="gemini",
                    save_image=False,
                    vector_store=store,
                    data_dir=data_dir,
                )
                second = await ingest_poster(
                    image_bytes=b"fake-image-2",
                    anime_title="Attack on Titan",
                    source="gemini",
                    save_image=False,
                    vector_store=store,
                    data_dir=data_dir,
                )

            self.assertTrue(first["success"])
            self.assertFalse(first["skipped_duplicate"])
            self.assertIsNone(first["poster_path"])

            self.assertTrue(second["success"])
            self.assertTrue(second["was_duplicate"])
            self.assertTrue(second["skipped_duplicate"])
            self.assertIsNone(second["index_id"])
            self.assertIsNone(second["poster_path"])
            self.assertEqual(second["index_size"], 1)
            self.assertEqual(second["slug"], first["slug"])
            self.assertEqual(store.index.ntotal, 1)
            self.assertEqual(len(store.metadata), 1)

            # High-similarity vector with a DIFFERENT anime title must NOT be skipped
            with patch("rag.ingestion.generate_embedding", new=AsyncMock(return_value=vec)):
                other = await ingest_poster(
                    image_bytes=b"fake-image-3",
                    anime_title="Attack on Titan: Final Season",
                    source="gemini",
                    save_image=False,
                    vector_store=store,
                    data_dir=data_dir,
                )
            self.assertTrue(other["success"])
            self.assertFalse(other["skipped_duplicate"])
            self.assertEqual(store.index.ntotal, 2)

    async def test_distinct_poster_same_anime_creates_alt_variant(self):
        vec1 = np.zeros(512, dtype="float32")
        vec1[0] = 1.0
        vec2 = np.zeros(512, dtype="float32")
        vec2[1] = 1.0

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            store = VectorStore(
                index_path=str(data_dir / "index.faiss"),
                metadata_path=str(data_dir / "posters.json"),
                dimension=512,
            )

            with patch("rag.ingestion.generate_embedding", new=AsyncMock(return_value=vec1)):
                first = await ingest_poster(
                    image_bytes=b"poster-1",
                    anime_title="Mob Psycho 100",
                    source="gemini",
                    save_image=False,
                    vector_store=store,
                    data_dir=data_dir,
                )

            with patch("rag.ingestion.generate_embedding", new=AsyncMock(return_value=vec2)):
                second = await ingest_poster(
                    image_bytes=b"poster-2",
                    anime_title="Mob Psycho 100",
                    source="gemini",
                    save_image=False,
                    vector_store=store,
                    data_dir=data_dir,
                )

            self.assertTrue(first["success"])
            self.assertTrue(second["success"])
            self.assertTrue(second["was_duplicate"])
            self.assertFalse(second["skipped_duplicate"])
            self.assertEqual(first["slug"], "mob_psycho_100")
            self.assertEqual(second["slug"], "mob_psycho_100_alt")
            self.assertEqual(store.index.ntotal, 2)
            self.assertEqual(store.id_to_slug, ["mob_psycho_100", "mob_psycho_100_alt"])
            self.assertEqual(store.search(vec1, k=1)[0].slug, "mob_psycho_100")
            self.assertEqual(store.search(vec2, k=1)[0].slug, "mob_psycho_100_alt")

    async def test_save_image_failure_still_succeeds_and_syncs_store(self):
        vec = _make_unit_vector(505)
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            store = VectorStore(
                index_path=str(data_dir / "index.faiss"),
                metadata_path=str(data_dir / "posters.json"),
                dimension=512,
            )

            with patch("rag.ingestion.generate_embedding", new=AsyncMock(return_value=vec)), \
                 patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
                result = await ingest_poster(
                    image_bytes=b"fake-image",
                    anime_title="Vinland Saga",
                    source="gemini",
                    save_image=True,
                    vector_store=store,
                    data_dir=data_dir,
                )

            self.assertTrue(result["success"])
            self.assertIsNone(result["poster_path"])
            self.assertEqual(store.index.ntotal, 1)

    def test_is_same_anime_slug_variants(self):
        self.assertTrue(_is_same_anime_slug("attack_on_titan", "attack_on_titan"))
        self.assertTrue(_is_same_anime_slug("attack_on_titan_alt", "attack_on_titan"))
        self.assertTrue(_is_same_anime_slug("attack_on_titan_alt2", "attack_on_titan"))
        self.assertFalse(_is_same_anime_slug("attack_on_titan_season_2", "attack_on_titan"))
        self.assertFalse(_is_same_anime_slug("attack_on_titan_alternative", "attack_on_titan"))

    def test_sync_from_happy_path_and_rejects_mismatched_store(self):
        vec = _make_unit_vector(404)
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            target = VectorStore(
                index_path=str(data_dir / "target.faiss"),
                metadata_path=str(data_dir / "target.json"),
                dimension=512,
            )
            source = VectorStore(
                index_path=str(data_dir / "source.faiss"),
                metadata_path=str(data_dir / "source.json"),
                dimension=512,
            )
            source.add_embedding("cowboy_bebop", vec)
            target.sync_from(source, {"cowboy_bebop": {"title": "Cowboy Bebop", "path": ""}})
            self.assertEqual(target.index.ntotal, 1)
            self.assertEqual(target.id_to_slug, ["cowboy_bebop"])

            bad_source = VectorStore(
                index_path=str(data_dir / "bad.faiss"),
                metadata_path=str(data_dir / "bad.json"),
                dimension=512,
            )
            bad_source.index.add(vec.reshape(1, -1))
            with self.assertRaises(ValueError):
                target.sync_from(bad_source, {})

            # Target state must remain intact after rejected sync
            self.assertEqual(target.index.ntotal, 1)
            self.assertEqual(target.id_to_slug, ["cowboy_bebop"])
            self.assertIn("cowboy_bebop", target.metadata)


if __name__ == "__main__":
    unittest.main()
