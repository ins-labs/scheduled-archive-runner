"""SOURCE ONLY until run in selected isolated NF venue. Mock boundary tests, not real-asset proof."""
import unittest,tempfile,pathlib,os,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
class DownloadAgeTests(unittest.TestCase):
 def scenario(self,fail):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);log=p/'calls'
   for name in ['curl','tar','sha256sum']:
    (p/name).write_text('#!/bin/sh\nprintf "%s\\n" "'+name+' $*" >> "$TEST_LOG"\n'+('exit 22\n' if fail==name else 'exit 0\n'))
    (p/name).chmod(0o700)
   r=subprocess.run(['/bin/bash',str(ROOT/'tools/download-age.sh')],env={'PATH':str(p)+':/usr/bin:/bin','TEST_LOG':str(log)},capture_output=True,text=True)
   return r.returncode,log.read_text().splitlines()
 def test_http_failure_stops_before_tar_and_checksum(self):
  rc,lines=self.scenario('curl');self.assertNotEqual(rc,0);self.assertEqual(len(lines),1);self.assertIn('--fail',lines[0])
 def test_nonarchive_stops_before_checksum_and_extraction(self):
  rc,lines=self.scenario('tar');self.assertNotEqual(rc,0);self.assertEqual(len(lines),2);self.assertIn('tar -tzf',lines[1])
 def test_checksum_failure_stops_before_extraction(self):
  rc,lines=self.scenario('sha256sum');self.assertNotEqual(rc,0);self.assertEqual(len(lines),3);self.assertIn('sha256sum -c -',lines[-1])
 def test_success_orders_http_archive_integrity_extract(self):
  rc,lines=self.scenario(None);self.assertEqual(rc,0);self.assertEqual(len(lines),4);self.assertIn('tar -xzf',lines[-1]);self.assertIn('v1.3.2',lines[0])
if __name__=='__main__':unittest.main()
