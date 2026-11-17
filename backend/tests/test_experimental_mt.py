from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT.parent / "ml_pipeline" / "scripts"))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from services import experimental_mt, hosted_mt  # noqa: E402
from settings import Settings, get_settings  # noqa: E402

# Zomi-side strings are placeholders, never real language data.


class FakeTokenizer:
    def __init__(self, vocab: dict[str, int]) -> None:
        self.vocab = vocab

    def get_vocab(self):
        return self.vocab

    def encode(self, text, add_special_tokens=False):
        return SimpleNamespace(tokens=text.split())

    def token_to_id(self, token):
        return self.vocab.get(token)

    def decode(self, ids, skip_special_tokens=True):
        names = {v: k for k, v in self.vocab.items()}
        return " ".join(names[i] for i in ids)


class FakeTranslator:
    def __init__(self) -> None:
        self.calls = []

    def translate_batch(self, batch, target_prefix, **kwargs):
        self.calls.append((batch[0], target_prefix[0]))
        return [SimpleNamespace(hypotheses=[[target_prefix[0][0], "ZOMI_OUT"]])]


VOCAB = {"</s>": 2, "eng_Latn": 5, "ZOMI_OUT": 9}


def translator(vocab=None) -> experimental_mt.ExperimentalTranslator:
    serving = {"name": "test-model", "version": "2026-10-28"}
    return experimental_mt.ExperimentalTranslator(FakeTranslator(), FakeTokenizer(vocab or {**VOCAB, "ctd_Latn": 7}), serving)


class TranslatorTests(unittest.TestCase):
    def test_language_tokens_in_both_directions(self) -> None:
        model = translator()
        self.assertEqual(model.translate("hello there", "en-ctd"), "ZOMI_OUT")
        self.assertEqual(model.translate("ZOMI_IN", "ctd-en"), "ZOMI_OUT")
        self.assertEqual(model.translator.calls, [
            (["eng_Latn", "hello", "there", "</s>"], ["ctd_Latn"]),
            (["ctd_Latn", "ZOMI_IN", "</s>"], ["eng_Latn"]),
        ])

    def test_models_trained_with_the_old_token_still_work(self) -> None:
        model = translator({**VOCAB, "zom_Latn": 6})
        self.assertEqual(model.tokens["ctd"], "zom_Latn")

    def test_tokenizer_without_zomi_is_refused(self) -> None:
        with self.assertRaises(experimental_mt.ModelNotServable):
            translator(VOCAB)

    def test_long_input_is_cut_to_the_model_limit(self) -> None:
        model = translator()
        model.translate(" ".join(["w"] * 500), "en-ctd")
        self.assertEqual(len(model.translator.calls[0][0]), experimental_mt.MAX_SOURCE_TOKENS + 2)


class ServingRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def serving(self, cleared: bool) -> Path:
        (self.dir / "serving.json").write_text(json.dumps({
            "name": "m", "version": "1", "cleared_for_serving": cleared,
            "uncleared_sources": [] if cleared else ["parallel_corpus"],
        }))
        return self.dir

    def settings(self, **values) -> Settings:
        return Settings(_env_file=None, **values)

    def test_cleared_model_is_served(self) -> None:
        with patch.object(experimental_mt, "get_settings", return_value=self.settings()):
            self.assertEqual(experimental_mt.read_serving(self.serving(True))["name"], "m")

    def test_uncleared_model_is_refused_unless_development_override(self) -> None:
        path = self.serving(False)
        with patch.object(experimental_mt, "get_settings", return_value=self.settings()):
            with self.assertRaisesRegex(experimental_mt.ModelNotServable, "parallel_corpus"):
                experimental_mt.read_serving(path)
        with patch.object(experimental_mt, "get_settings",
                          return_value=self.settings(environment="development", experimental_mt_allow_uncleared=True)):
            self.assertEqual(experimental_mt.read_serving(path)["name"], "m")

    def test_override_is_rejected_outside_development(self) -> None:
        with self.assertRaisesRegex(ValueError, "only allowed in development"):
            self.settings(environment="production", database_url="postgresql+psycopg://x@localhost/x",
                          experimental_mt_allow_uncleared=True)

    def test_missing_serving_record_is_refused(self) -> None:
        with patch.object(experimental_mt, "get_settings", return_value=self.settings()):
            with self.assertRaises(experimental_mt.ModelNotServable):
                experimental_mt.read_serving(self.dir)


class EndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        experimental_mt._loaded.cache_clear()

    def test_unavailable_when_not_enabled(self) -> None:
        unavailable = (None, experimental_mt.Status(False, "Experimental machine translation is not enabled."))
        with patch.object(experimental_mt, "_loaded", return_value=unavailable):
            status = self.client.get("/api/v1/translate/experimental").json()
            response = self.client.post("/api/v1/translate/experimental", json={"text": "hello"})
        self.assertFalse(status["available"])
        self.assertEqual(response.status_code, 503)

    def test_translation_is_labelled_experimental_with_its_model(self) -> None:
        model = translator()
        loaded = (model, experimental_mt.Status(True, "ok", model.name, model.version))
        with patch.object(experimental_mt, "_loaded", return_value=loaded):
            status = self.client.get("/api/v1/translate/experimental").json()
            body = self.client.post("/api/v1/translate/experimental",
                                    json={"text": "hello", "direction": "en-zom"}).json()
        self.assertEqual((status["available"], status["system"]), (True, "test-model"))
        self.assertEqual(body["translation"], "ZOMI_OUT")
        self.assertTrue(body["experimental"])
        self.assertEqual(body["label"], experimental_mt.LABEL)
        self.assertIn("not a verified translation", body["note"])
        self.assertEqual((body["system"], body["system_version"], body["direction"]),
                         ("test-model", "2026-10-28", "en-ctd"))

    def test_input_length_is_limited(self) -> None:
        response = self.client.post("/api/v1/translate/experimental", json={"text": "x" * 501})
        self.assertEqual(response.status_code, 422)

    def test_retrieval_translate_is_unchanged(self) -> None:
        self.assertNotIn("experimental", self.client.post("/api/v1/translate", json={"text": "water"}).json())


class HostedEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        configured = Settings(
            experimental_mt_openai_api_key="test-key",
            experimental_mt_openai_model="test-model",
        )
        config = patch.object(hosted_mt, "get_settings", return_value=configured)
        config.start()
        self.addCleanup(config.stop)

    def test_generation_forwards_submitted_text_in_both_directions(self) -> None:
        route = "/api/v1/translate/experimental"
        self.assertEqual(self.client.get(route).json()["system"], "OpenAI")
        for direction, source in [("en-ctd", "English"), ("ctd-en", "Tedim-based Zomi")]:
            with self.subTest(direction=direction):
                provider_response = {
                    "status": "completed",
                    "model": "test-model-snapshot",
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": "GENERATED"}]}],
                }
                with patch.object(hosted_mt, "urlopen", return_value=io.BytesIO(json.dumps(provider_response).encode())) as send:
                    response = self.client.post(route, json={"text": "INPUT", "direction": direction})
                request = send.call_args.args[0]
                payload = json.loads(request.data)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["translation"], "GENERATED")
                self.assertEqual(response.json()["system_version"], "test-model-snapshot")
                self.assertTrue(response.json()["experimental"])
                self.assertEqual(payload["input"], "INPUT")
                self.assertIn(f"Translate from {source}", payload["instructions"])
                self.assertFalse(payload["store"])

    def test_provider_error_does_not_return_retrieved_or_private_text(self) -> None:
        with patch.object(hosted_mt, "urlopen", side_effect=URLError("PRIVATE UPSTREAM ERROR")):
            response = self.client.post("/api/v1/translate/experimental", json={"text": "INPUT"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("PRIVATE", response.text)
        self.assertNotIn("translation", response.json())

    def test_hosted_configuration_is_rejected_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "only available in development"):
            Settings(environment="production", experimental_mt_openai_model="test-model")


@unittest.skipUnless(os.getenv("SIAMSIL_TEST_MT_DIR"), "set SIAMSIL_TEST_MT_DIR to an exported model to run")
class RealModelTests(unittest.TestCase):
    def test_exported_model_translates_both_directions(self) -> None:
        get_settings.cache_clear()
        with patch.dict(os.environ, {"SIAMSIL_EXPERIMENTAL_MT_ALLOW_UNCLEARED": "true"}):
            model = experimental_mt.load(Path(os.environ["SIAMSIL_TEST_MT_DIR"]))
        get_settings.cache_clear()
        self.assertTrue(model.translate("Good morning", "en-ctd"))
        self.assertTrue(model.translate("Good morning", "ctd-en"))


if __name__ == "__main__":
    unittest.main()
