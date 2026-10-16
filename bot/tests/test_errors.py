"""Erros -> mensagem de cliente; status de reserva -> rotulo."""
import unittest

from app.infotravel.errors import client_message_for_avail_error, status_para_cliente


class TestErros(unittest.TestCase):
    def test_1278_nao_diz_sem_oferta(self):
        msg = client_message_for_avail_error(400, {"exceptionCode": 1278,
                                                   "message": "Destino não encontrado"})
        self.assertIn("catalogo", msg)
        self.assertNotIn("disponibilidade", msg.lower())

    def test_no_availability_oferece_periodos(self):
        msg = client_message_for_avail_error(400, {"message": "No availability"})
        self.assertIn("periodos", msg)

    def test_500_nao_vaza_detalhe(self):
        msg = client_message_for_avail_error(500, {"stack": "NullPointer..."})
        self.assertNotIn("NullPointer", msg)

    def test_status_desconhecido_nao_quebra(self):
        self.assertEqual(status_para_cliente("ALGO_NOVO_2030"), "em verificacao")
        self.assertEqual(status_para_cliente("QUOTATION"), "em processamento")
        self.assertEqual(status_para_cliente("CONFIRMED"), "confirmada")


if __name__ == "__main__":
    unittest.main()
