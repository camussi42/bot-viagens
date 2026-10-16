"""Regressao critica: Sao Paulo regiao (2802) NUNCA pode virar municipio (23500).

O catalogo de pacotes so devolve ids do espaco correto (regiao/aeroporto),
entao o casamento por nome acontece sobre opcoes seguras por construcao.
"""
import unittest

from app.infotravel.catalog import CatalogClient, Opcao


class FakeApi:
    def call(self, method, path, params=None, body=None):
        if path.endswith("/destination"):
            return {"destinations": [
                {"id": 2802, "name": "São Paulo, São Paulo, Brasil", "type": "M"},
                {"id": 15767, "name": "São Paulo, ...", "type": "M"},
            ]}
        if path.endswith("/period"):
            return {"periods": [{"start": "2026-09-12",
                                 "endDates": ["2026-09-17", "2026-09-19"]}]}
        return {"origins": [
            {"id": 2732, "name": "Rio de Janeiro, ...", "type": "M", "iata": "RIO"},
            {"id": 8249, "name": "Aeroporto GIG", "type": "A", "iata": "GIG"},
        ]}


class TestRegiaoSegura(unittest.TestCase):
    def setUp(self):
        self.cat = CatalogClient(FakeApi())

    def test_destino_sao_paulo_resolve_regiao_2802(self):
        opcoes = self.cat.destinos("hotel_flight", 2732, "M")
        achada = CatalogClient.achar_por_nome(opcoes, "São Paulo, São Paulo, Brasil")
        self.assertIsNotNone(achada)
        self.assertEqual(achada.id, 2802)
        self.assertNotEqual(achada.id, 23500)  # municipio: jamais!

    def test_ambiguidade_nao_chuta(self):
        opcoes = [Opcao(1, "São Paulo A", "M"), Opcao(2, "São Paulo B", "M")]
        self.assertIsNone(CatalogClient.achar_por_nome(opcoes, "São Paulo"))

    def test_periodos_normalizados(self):
        periodos = self.cat.periodos("hotel_flight", 2732, "M", 2802, "M")
        self.assertEqual(periodos[0]["start"], "2026-09-12")
        self.assertIn("2026-09-17", periodos[0]["ends"])

    def test_tipo_invalido_levanta(self):
        with self.assertRaises(ValueError):
            self.cat.origens("foguete")


if __name__ == "__main__":
    unittest.main()
