"""Teste e2e ON-LINE (offline): fluxo /v1/turn com QuoteClient mockado."""
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app.infotravel.settings import InfotravelSettings
from app.service import BotService


class TestInfotravelE2E(unittest.TestCase):
    """Simula o serviço com o cotador mockado, sem touchar rede.

    O objetivo e validar a ponte HTTP /v1/turn e o fluxo de cotação (cotando ->
    orcamento), deixando a chamada externa sempre mockada (offline by default).
    """

    HOJE = date(2026, 9, 20)

    def _service(self):
        quote = MagicMock()
        quote.disponibilidade.return_value = {
            "packageAvails": [
                {
                    "package": {"id": "p1", "name": "Pacote Gramado", "start": "2026-09-12",
                                "end": "2026-09-17", "lowestFare": "2200"},
                    "hotelAvails": [
                        {
                            "hotel": {"id": "h1", "name": "Hotel Colonial"},
                            "lowestFare": "1800",
                        }
                    ],
                }
            ]
        }
        quote.orcamento.return_value = {
            "id": "orc-1", "status": "QUOTATION",
            "total": "2000.00", "currency": "BRL", "bookingRq": {},
        }
        return BotService(
            settings=InfotravelSettings(domain="x", username="y", password="z",
                              client="c", agency="2"),
            api_client=MagicMock(),
            catalog=MagicMock(),
            quote=quote,
            hoje=lambda: self.HOJE,
        )

    def _turn(self, bot, wa, texto):
        self._msg_n = getattr(self, "_msg_n", 0) + 1
        return bot.turno({"wa_id": wa, "name": "T"}, {"id": f"m-{wa}-{self._msg_n}", "type": "text", "text": texto})

    def test_message_completa_vai_para_confirmacao(self):
        bot = self._service()
        r = self._turn(bot, "5511k", "quero hotel em Gramado 12 a 17 de setembro, 2 adultos")
        self.assertEqual(r["state"]["stage"], "confirmando")
        # confirmacao retorna acao de texto + botoes
        self.assertEqual(len(r["actions"]), 2)

    def test_cotacao_sim_chama_disponibilidade(self):
        bot = self._service()
        r = self._turn(bot, "5511l", "quero hotel em Gramado 12 a 17 de setembro, 2 adultos")
        self.assertEqual(r["state"]["stage"], "confirmando")
        r2 = self._turn(bot, "5511l", "sim")
        self.assertEqual(r2["state"]["stage"], "proposta")
        # disponibilidade e chamada (checkRate/budget so e chamado ao confirmar preco)
        bot._cotador().disponibilidade.assert_called_once()
        bot._cotador().orcamento.assert_not_called()

    def test_sem_credenciais_avisa_e_nao_chama_api(self):
        bot = BotService()
        r = self._turn(bot, "5511m", "quero hotel em Gramado 12 a 17 de setembro, 2 adultos")
        self.assertEqual(r["state"]["stage"], "confirmando")
        r2 = self._turn(bot, "5511m", "sim")
        self.assertEqual(r2["state"]["stage"], "confirmando")
        self.assertIn("credenciais", r2["actions"][0]["text"].lower())

    def test_handoff_previne_cotacao(self):
        bot = self._service()
        r = self._turn(bot, "5511n", "falar com um atendente")
        self.assertTrue(r["handoff"])
        self.assertFalse(bot._cotador().orcamento.called)


if __name__ == "__main__":
    unittest.main()
