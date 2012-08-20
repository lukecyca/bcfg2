import os
import stat
import copy
import unittest
import lxml.etree
from mock import Mock, MagicMock, patch
from Bcfg2.Client.Tools.POSIX.Directory import *
from Test__init import get_posix_object
from Testbase import TestPOSIXTool
from .....common import *

class TestPOSIXDirectory(TestPOSIXTool):
    test_obj = POSIXDirectory

    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.verify")
    @patch("Bcfg2.Client.Tools.POSIX.Directory.%s._exists" % test_obj.__name__)
    def test_verify(self, mock_exists, mock_verify):
        entry = lxml.etree.Element("Path", name="/test", type="directory",
                                   perms='0644', owner='root', group='root')
        ptool = self.get_obj()

        mock_exists.return_value = False
        self.assertFalse(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)

        mock_exists.reset_mock()
        exists_rv = MagicMock()
        exists_rv.__getitem__.return_value = stat.S_IFREG | 0644
        mock_exists.return_value = exists_rv
        self.assertFalse(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)

        mock_exists.reset_mock()
        mock_verify.return_value = False
        exists_rv.__getitem__.return_value = stat.S_IFDIR | 0644
        self.assertFalse(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])

        mock_exists.reset_mock()
        mock_verify.reset_mock()
        mock_verify.return_value = True
        self.assertTrue(ptool.verify(entry, []))
        mock_exists.assert_called_with(entry)
        mock_verify.assert_called_with(ptool, entry, [])

        with patch("os.listdir") as mock_listdir:
            mock_exists.reset_mock()
            mock_verify.reset_mock()
            entry.set("prune", "true")
            orig_entry = copy.deepcopy(entry)

            entries = ["foo", "bar", "bar/baz"]
            mock_listdir.return_value = entries
            modlist = [os.path.join(entry.get("name"), entries[0])]
            self.assertFalse(ptool.verify(entry, modlist))
            mock_exists.assert_called_with(entry)
            mock_verify.assert_called_with(ptool, entry, modlist)
            mock_listdir.assert_called_with(entry.get("name"))
            expected = [os.path.join(entry.get("name"), e)
                        for e in entries
                        if os.path.join(entry.get("name"), e) not in modlist]
            actual = [e.get("path") for e in entry.findall("Prune")]
            self.assertItemsEqual(expected, actual)
            
            mock_verify.reset_mock()
            mock_exists.reset_mock()
            mock_listdir.reset_mock()
            entry = copy.deepcopy(orig_entry)
            modlist = [os.path.join(entry.get("name"), e)
                       for e in entries]
            self.assertTrue(ptool.verify(entry, modlist))
            mock_exists.assert_called_with(entry)
            mock_verify.assert_called_with(ptool, entry, modlist)
            mock_listdir.assert_called_with(entry.get("name"))
            self.assertEqual(len(entry.findall("Prune")), 0)
    
    @patch("os.unlink")
    @patch("shutil.rmtree")
    @patch("Bcfg2.Client.Tools.POSIX.base.POSIXTool.install")
    @patch("Bcfg2.Client.Tools.POSIX.Directory.%s._exists" % test_obj.__name__)
    @patch("Bcfg2.Client.Tools.POSIX.Directory.%s._makedirs" %
           test_obj.__name__)
    def test_install(self, mock_makedirs, mock_exists, mock_install,
                     mock_rmtree, mock_unlink):
        entry = lxml.etree.Element("Path", name="/test/foo/bar",
                                   type="directory", perms='0644',
                                   owner='root', group='root')
        ptool = self.get_obj()
        
        def reset():
            mock_exists.reset_mock()
            mock_install.reset_mock()
            mock_unlink.reset_mock()
            mock_rmtree.reset_mock()
            mock_rmtree.mock_makedirs()

        mock_makedirs.return_value = True
        mock_exists.return_value = False
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_exists.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)
        mock_makedirs.assert_called_with(entry)

        reset()
        exists_rv = MagicMock()
        exists_rv.__getitem__.return_value = stat.S_IFREG | 0644
        mock_exists.return_value = exists_rv
        self.assertTrue(ptool.install(entry))
        mock_unlink.assert_called_with(entry.get("name"))
        mock_exists.assert_called_with(entry)
        mock_makedirs.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)

        reset()
        exists_rv.__getitem__.return_value = stat.S_IFDIR | 0644
        mock_install.return_value = True
        self.assertTrue(ptool.install(entry))
        mock_exists.assert_called_with(entry)
        mock_install.assert_called_with(ptool, entry)

        reset()
        mock_install.return_value = False
        self.assertFalse(ptool.install(entry))
        mock_install.assert_called_with(ptool, entry)

        entry.set("prune", "true")
        prune = ["/test/foo/bar/prune1", "/test/foo/bar/prune2"]
        for path in prune:
            lxml.etree.SubElement(entry, "Prune", path=path)
        
        reset()
        mock_install.return_value = True
        with patch("os.path.isdir") as mock_isdir:
            def isdir_rv(path):
                if path.endswith("prune2"):
                    return True
                else:
                    return False
            mock_isdir.side_effect = isdir_rv
            self.assertTrue(ptool.install(entry))
            mock_exists.assert_called_with(entry)
            mock_install.assert_called_with(ptool, entry)
            self.assertItemsEqual(mock_isdir.call_args_list,
                                  [call(p) for p in prune])
            mock_unlink.assert_called_with("/test/foo/bar/prune1")
            mock_rmtree.assert_called_with("/test/foo/bar/prune2")