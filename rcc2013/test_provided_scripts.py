import unittest
from provided_scripts import prepare, source


class ProvidedScriptTests(unittest.TestCase):
    def job(self):
        return dict(width=512,height=512,base_url='http://127.0.0.1:8123',
                    upload_url='http://127.0.0.1:8123/upload',
                    avatar={'assets':[],'bodyColors':{'headColorId':24}},
                    job_id='owned-"\\\n☃',access_key='local-test',user_id=2)

    def test_originals_are_pinned_and_job_parameters_cannot_add_lua(self):
        for kind in ('headshot','full_body'):
            original=source(kind)
            lua=prepare(kind,**self.job())
            self.assertIn('http://ech.qzz.io',original)
            self.assertNotIn('ech.qzz.io',lua)
            self.assertNotIn('UPLOAD_URL_HERE',lua)
            self.assertNotIn('JSON_AVATAR',lua)
            self.assertNotIn('_X_RES_',lua)
            self.assertNotIn('Instance.New(',lua)
            self.assertIn('owned-\\034\\092\\010\\226\\152\\131',lua)
            self.assertIn("ThumbnailGenerator:Click('png', 512, 512, true, "+('true)' if kind=='headshot' else 'false)'),lua)
        self.assertIn('render(userId)',prepare('full_body',**self.job()))

    def test_rejects_nonlocal_endpoints_and_executable_dimensions(self):
        for changes in ({'upload_url':'https://example.org/upload'},
                        {'base_url':'http://127.0.0.1@example.org'},
                        {'width':'512);error("oops")'},
                        {'user_id':True}):
            with self.assertRaises(ValueError):prepare('headshot',**{**self.job(),**changes})


if __name__=='__main__':unittest.main()
