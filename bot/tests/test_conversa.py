"""Conversa ponta a ponta OFFLINE (heuristica, sem LLM, sem API).

Cenarios: mensagem completa -> confirmacao; mensagens fragmentadas com
memoria; pedido de humano -> handoff; dedupe; botoes.
"""
import unittest
from datetime import date

from app.service import BotService

HOJE = date(2026, 9, 20)


def svc():
    return BotService(hoje=lambda: HOJE)


def texto(bot, wa, mensagem):
    return bot.turno({"wa_id": wa, "name": "Teste"},
                     {"id": f"m-{mensagem[:8]}-{wa}", "type": "text", "text": mensagem})


class TestConversaCompleta(unittest.TestCase):
    def test_mensagem_completa_vai_para_confirmacao(self):
        bot = svc()
        r1 = texto(bot, "5511a", "quero pacote hotel + aéreo para Gramado")
        self.assertEqual(r1["state"]["stage"], "coletando")
        r2 = texto(bot, "5511a", "saindo de São Paulo, 12 a 17 de setembro, "
                                 "2 adultos e 1 criança de 9 anos")
        self.assertEqual(r2["state"]["stage"], "confirmando")
        acao = r2["actions"][0]["text"]
        self.assertIn("Gramado", acao)
        self.assertIn("Confirma", acao)

    def test_memoria_entre_mensagens(self):
        bot = svc()
        texto(bot, "5511b", "oi, quero hotel + aéreo")
        r = texto(bot, "5511b", "para Gramado")
        self.assertNotIn("destino", r["state"].get("faltando", []))
        # destino preenchido; pergunta seguinte nao e mais destino
        acoes = " ".join(a.get("text", "") for a in r["actions"])
        self.assertNotIn("Para qual destino", acoes)

    def test_nao_repete_pergunta_respondida(self):
        bot = svc()
        texto(bot, "5511c", "quero hotel em Gramado, 12 a 17 de setembro, 2 adultos")
        r = texto(bot, "5511c", "sim")
        self.assertEqual(r["state"]["stage"], "confirmando")

    def test_humano(self):
        bot = svc()
        r = texto(bot, "5511d", "quero falar com um atendente")
        self.assertTrue(r["handoff"])
        self.assertEqual(r["state"]["stage"], "humano")

    def test_dedupe(self):
        bot = svc()
        contato = {"wa_id": "5511e", "name": "T"}
        m = {"id": "mesmo-id", "type": "text", "text": "oi"}
        r1 = bot.turno(contato, m)
        r2 = bot.turno(contato, dict(m))
        self.assertTrue(r2.get("duplicada"))
        self.assertEqual(r2["actions"], [])

    def test_botoes(self):
        bot = svc()
        texto(bot, "5511f", "oi")
        r = bot.turno({"wa_id": "5511f", "name": "T"},
                      {"id": "b1", "type": "button", "button_id": "tipo:hotel_flight",
                       "text": "Hotel + aéreo"})
        self.assertFalse(any("O que você procura" in a.get("text", "")
                             for a in r["actions"]))

    def test_sem_credenciais_cotar_avisa(self):
        bot = svc()
        texto(bot, "5511g", "quero hotel em Gramado, 12 a 17 de setembro, 2 adultos")
        r = texto(bot, "5511g", "sim")
        # 'sim' leva a COTANDO; sem credenciais volta p/ CONFIRMANDO com aviso
        self.assertEqual(r["state"]["stage"], "confirmando")
        self.assertIn("credenciais", r["actions"][0]["text"].lower())


if __name__ == "__main__":
    unittest.main()
