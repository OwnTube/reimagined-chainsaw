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

class PropertyEvidenceTests(unittest.TestCase):
    def test_requires_actual_scene_property_matching_server_only_nonce(self):
        from verify_owned_schema import verify_property
        nonce='RCC2013_'+'a1'*16
        server={'property_probe':{'sent':True,'class_name':'TestService','property_name':'Instance:Name','nonce':nonce}}
        lines=['owned|SERVICE_NAME|TestService|'+nonce]
        self.assertTrue(verify_property(server,lines)['property_replication_validated'])
        self.assertFalse(verify_property(server,[])['property_replication_validated'])
        self.assertFalse(verify_property(server,['owned|SERVICE_NAME|Workspace|'+nonce])['property_replication_validated'])
        self.assertFalse(verify_property(server,['owned|SERVICE_NAME|TestService|RCC2013_'+'b2'*16])['property_replication_validated'])
        self.assertFalse(verify_property(server,lines)['world_replication_validated'])
        self.assertFalse(verify_property(server,lines)['game_join_validated'])

class InstanceEvidenceTests(unittest.TestCase):
    def test_requires_native_object_value_guid_class_and_parent(self):
        from verify_owned_schema import verify_instance
        nonce='RCC2013_'+'a1'*16
        server={'owned_instance_probe':{'sent':True,'class_name':'StringValue','name':'RccServerToken','nonce':nonce,
                                       'index':0x23456789,'parent_index':0x3456789a},
                'globals_bindings':[{'class_name':'Workspace','index':0x3456789a}]}
        lines=['owned|OWNED_STRINGVALUE|Workspace|StringValue|RccServerToken|'+nonce+'|'+str(0x23456789)]
        result=verify_instance(server,lines)
        self.assertTrue(result['new_instance_replication_validated'])
        self.assertFalse(result['game_join_validated'])
        self.assertFalse(verify_instance(server,[])['new_instance_replication_validated'])
        for before,after in [('Workspace','ReplicatedStorage'),('StringValue','Part'),(str(0x23456789),str(0x23456788)),(nonce,'RCC2013_'+'b2'*16)]:
            self.assertFalse(verify_instance(server,[lines[0].replace(before,after)])['new_instance_replication_validated'])
        server['owned_instance_probe']['parent_index']=0x3456789b
        self.assertFalse(verify_instance(server,lines)['new_instance_replication_validated'])
