import copy
import unittest
from verify_owned_schema import verify_delivery,OWNED_SCHEMA_SHA256

class DeliveryEvidenceTests(unittest.TestCase):
    def test_acknowledged_schema_does_not_prove_application_or_world(self):
        server={'schema_delivery':{'queued':True,'all_fragments_acked':True,'bits':320080,
                                  'bytes':40010,'sha256':OWNED_SCHEMA_SHA256}}
        result=verify_delivery(server)
        self.assertTrue(result['transport_delivery_validated'])
        for field in ('application_acceptance_validated','world_replication_validated','game_join_validated'):
            self.assertFalse(result[field])
        for field,value in [('queued',False),('all_fragments_acked',False),('bits',320079),('bytes',40009),('sha256','0'*64)]:
            altered=copy.deepcopy(server);altered['schema_delivery'][field]=value
            self.assertFalse(verify_delivery(altered)['transport_delivery_validated'])
        self.assertFalse(verify_delivery({})['transport_delivery_validated'])

if __name__=='__main__':unittest.main()
