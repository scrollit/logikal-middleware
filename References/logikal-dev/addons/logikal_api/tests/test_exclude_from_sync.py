# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestExcludeFromSync(TransactionCase):
    """Test cases for the exclude from sync functionality"""

    def setUp(self):
        super().setUp()
        # Create test folders
        self.root_folder = self.env['mbioe.folder'].with_context(from_mbioe_sync=True).create({
            'name': 'Test Root',
            'identifier': 'test-root-001',
            'full_path': 'Test Root',
            'exclude_from_sync': False,
        })
        
        self.child_folder = self.env['mbioe.folder'].with_context(from_mbioe_sync=True).create({
            'name': 'Test Child',
            'identifier': 'test-child-001',
            'full_path': 'Test Root/Test Child',
            'parent_id': self.root_folder.id,
            'exclude_from_sync': False,
        })
        
        self.grandchild_folder = self.env['mbioe.folder'].with_context(from_mbioe_sync=True).create({
            'name': 'Test Grandchild',
            'identifier': 'test-grandchild-001',
            'full_path': 'Test Root/Test Child/Test Grandchild',
            'parent_id': self.child_folder.id,
            'exclude_from_sync': False,
        })

    def test_exclude_from_sync_field_exists(self):
        """Test that the exclude_from_sync field exists and works"""
        # Test default value
        self.assertFalse(self.root_folder.exclude_from_sync)
        
        # Test setting value
        self.root_folder.exclude_from_sync = True
        self.assertTrue(self.root_folder.exclude_from_sync)

    def test_sync_status_display_computed(self):
        """Test that sync_status_display is computed correctly"""
        # Test included status
        self.assertEqual(self.root_folder.sync_status_display, 'included')
        
        # Test excluded status
        self.root_folder.exclude_from_sync = True
        self.assertEqual(self.root_folder.sync_status_display, 'excluded')

    def test_is_excluded_from_sync_method(self):
        """Test the is_excluded_from_sync helper method"""
        # Initially not excluded
        self.assertFalse(self.grandchild_folder.is_excluded_from_sync())
        
        # Exclude parent folder
        self.child_folder.exclude_from_sync = True
        
        # Grandchild should now be excluded via parent
        self.assertTrue(self.grandchild_folder.is_excluded_from_sync())

    def test_get_excluded_subfolders_method(self):
        """Test the get_excluded_subfolders helper method"""
        # Initially no excluded subfolders
        excluded = self.root_folder.get_excluded_subfolders()
        self.assertEqual(len(excluded), 0)
        
        # Exclude child folder
        self.child_folder.exclude_from_sync = True
        
        # Should find excluded child
        excluded = self.root_folder.get_excluded_subfolders()
        self.assertEqual(len(excluded), 1)
        self.assertIn(self.child_folder, excluded)

    def test_action_toggle_sync_exclusion(self):
        """Test the toggle sync exclusion action"""
        # Initially included
        self.assertFalse(self.root_folder.exclude_from_sync)
        
        # Toggle to excluded
        result = self.root_folder.action_toggle_sync_exclusion()
        self.assertTrue(self.root_folder.exclude_from_sync)
        self.assertEqual(result['type'], 'ir.actions.client')
        
        # Toggle back to included
        result = self.root_folder.action_toggle_sync_exclusion()
        self.assertFalse(self.root_folder.exclude_from_sync)

    def test_bulk_exclude_action(self):
        """Test bulk exclude action"""
        folders = self.root_folder + self.child_folder
        
        # Test bulk exclude
        result = self.env['mbioe.folder'].with_context(
            active_ids=folders.ids
        ).action_bulk_exclude_from_sync()
        
        self.assertTrue(self.root_folder.exclude_from_sync)
        self.assertTrue(self.child_folder.exclude_from_sync)
        self.assertEqual(result['type'], 'ir.actions.client')

    def test_bulk_include_action(self):
        """Test bulk include action"""
        # First exclude folders
        self.root_folder.exclude_from_sync = True
        self.child_folder.exclude_from_sync = True
        
        folders = self.root_folder + self.child_folder
        
        # Test bulk include
        result = self.env['mbioe.folder'].with_context(
            active_ids=folders.ids
        ).action_bulk_include_in_sync()
        
        self.assertFalse(self.root_folder.exclude_from_sync)
        self.assertFalse(self.child_folder.exclude_from_sync)
        self.assertEqual(result['type'], 'ir.actions.client')

    def test_write_protection_still_works(self):
        """Test that write protection still works for other fields"""
        # Should not be able to modify readonly fields manually
        with self.assertRaises(UserError):
            self.root_folder.write({'name': 'Modified Name'})
        
        # But should be able to modify exclude_from_sync
        self.root_folder.write({'exclude_from_sync': True})
        self.assertTrue(self.root_folder.exclude_from_sync)

    def test_folder_creation_still_protected(self):
        """Test that folder creation is still protected"""
        # Should not be able to create folders without sync context
        with self.assertRaises(UserError):
            self.env['mbioe.folder'].create({
                'name': 'Manual Folder',
                'identifier': 'manual-001',
                'full_path': 'Manual Folder',
            })
