"""Teste do endpoint HTTP /v1/turn via FastAPI TestClient."""
import unittest

from fastapi.testclient import TestClient

from app import webapp


class TestWebapp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(webapp.app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["ok"], True)

    def test_turn_mensagem_completa(self):
        r = self.client.post("/v1/turn", json={"wa_id": "5511h", "text": "Quero pacote hotel + aéreo para Gramado"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["state"]["stage"], "coletando")
        self.assertTrue(body["actions"])

    def test_turn_sem_texto_erro(self):
        r = self.client.post("/v1/turn", json={"wa_id": "5511i", "text": "   "})
        self.assertEqual(r.status_code, 400)

    def test_turn_handoff(self):
        r = self.client.post("/v1/turn", json={"wa_id": "5511j", "text": "falar com um atendente"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["handoff"])


if __name__ == "__main__":
    unittest.main()
