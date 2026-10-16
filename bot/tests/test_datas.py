"""Datas em pt-BR: numericas, por extenso, relativas e periodos."""
import unittest
from datetime import date

from app.conversation import dates
from app.conversation.extract import parse_cidades, parse_periodo

HOJE = date(2026, 9, 10)  # quinta; setembro ainda e futuro


class TestParseData(unittest.TestCase):
    def test_numerica_com_ano(self):
        self.assertEqual(dates.parse_data("12/09/2026", HOJE), "2026-09-12")

    def test_numerica_sem_ano_futuro(self):
        self.assertEqual(dates.parse_data("dia 12", HOJE), "2026-09-12")

    def test_extenso(self):
        self.assertEqual(dates.parse_data("12 de setembro", HOJE), "2026-09-12")

    def test_extenso_passado_vai_proximo_ano(self):
        self.assertEqual(dates.parse_data("10 de janeiro", HOJE), "2027-01-10")

    def test_relativas(self):
        self.assertEqual(dates.parse_data("amanhã", HOJE), "2026-09-11")
        self.assertEqual(dates.parse_data("semana que vem", HOJE), "2026-09-14")

    def test_invalida_retorna_none(self):
        self.assertIsNone(dates.parse_data("quando der", HOJE))


class TestPeriodo(unittest.TestCase):
    def test_mes(self):
        self.assertEqual(parse_periodo("12 a 17 de setembro", HOJE),
                         ("2026-09-12", "2026-09-17"))

    def test_meses_diferentes(self):
        self.assertEqual(parse_periodo("28 de junho a 3 de julho", HOJE),
                         ("2027-06-28", "2027-07-03"))

    def test_numerico(self):
        self.assertEqual(parse_periodo("12/09 a 17/09", HOJE),
                         ("2026-09-12", "2026-09-17"))


class TestOcupacaoTexto(unittest.TestCase):
    def test_adultos(self):
        self.assertEqual(dates.parse_adultos("somos 2 adultos"), 2)
        self.assertEqual(dates.parse_adultos("viajo sozinho"), 1)

    def test_idades(self):
        self.assertEqual(dates.parse_idades_criancas("1 criança de 9 anos"), [9])
        self.assertEqual(dates.parse_idades_criancas("filhos de 4 e 7 anos"), [4, 7])


class TestCidades(unittest.TestCase):
    def test_origem_destino(self):
        origem, destino = parse_cidades("saindo de São Paulo para Gramado em setembro")
        self.assertEqual(origem, "São Paulo")
        self.assertEqual(destino, "Gramado")

    def test_nao_confunde_data_com_cidade(self):
        _, destino = parse_cidades("quero ir para Gramado dia 12")
        self.assertEqual(destino, "Gramado")


if __name__ == "__main__":
    unittest.main()
