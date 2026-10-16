"""Slots: merge sem regressao, pendencias, occupancy, conversao p/ cotacao."""
import unittest

from app.conversation import slots
from app.infotravel.quote import montar_occupancy


class TestMerge(unittest.TestCase):
    def test_nao_regride_confirmado(self):
        est = slots.novo_estado()
        est = slots.atualizar(est, {"destino": {"texto": "Gramado", "confianca": 1.0,
                                                "origem": "cliente"}})
        est2 = slots.atualizar(est, {"destino": {"texto": "Canela", "confianca": 0.6,
                                                 "origem": "heuristica"}})
        self.assertEqual(est2["destino"]["texto"], "Gramado")

    def test_maior_confianca_vence(self):
        est = slots.novo_estado()
        est = slots.atualizar(est, {"destino": {"texto": "Gramado", "confianca": 0.6,
                                                "origem": "heuristica"}})
        est = slots.atualizar(est, {"destino": {"texto": "Canela", "confianca": 1.0,
                                                "origem": "cliente"}})
        self.assertEqual(est["destino"]["texto"], "Canela")

    def test_faltando_ordem(self):
        est = slots.novo_estado()
        self.assertEqual(slots.faltando(est),
                         ["package_type", "destino", "data_inicio", "data_fim", "adultos"])


class TestOccupancy(unittest.TestCase):
    def test_simples(self):
        self.assertEqual(montar_occupancy({"adultos": 2}), ["2"])

    def test_com_criancas(self):
        self.assertEqual(montar_occupancy({"adultos": 2, "criancas_idades": [9, 4]}), ["2-9,4"])

    def test_sem_adulto_levanta(self):
        with self.assertRaises(ValueError):
            montar_occupancy({"adultos": 0})

    def test_para_cotacao(self):
        est = slots.novo_estado()
        est = slots.atualizar(est, {
            "data_inicio": {"iso": "2026-09-12", "confianca": 1.0},
            "data_fim": {"iso": "2026-09-17", "confianca": 1.0},
            "origem": {"id": 2732, "tipo": "M", "confianca": 1.0},
            "destino": {"id": 15767, "tipo": "M", "confianca": 1.0},
            "adultos": {"valor": 2, "confianca": 1.0},
            "criancas_idades": {"valor": [9], "confianca": 1.0}})
        cfg = slots.para_cotacao(est)
        self.assertEqual(cfg["origem"], {"id": 2732, "tipo": "M"})
        self.assertEqual(cfg["ocupacao"], {"adultos": 2, "criancas_idades": [9], "quartos": 1})


if __name__ == "__main__":
    unittest.main()
