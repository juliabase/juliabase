from django.test import SimpleTestCase
from unittest.mock import MagicMock
from samples.data_tree import DataNode

class DataNodeTests(SimpleTestCase):
    def test_init_with_string(self):
        node = DataNode("test_name")
        self.assertEqual(node.name, "test_name")
        self.assertEqual(node.descriptive_name, "test_name")
        self.assertEqual(node.items, [])
        self.assertEqual(node.children, [])

    def test_init_with_instance(self):
        mock_instance = MagicMock()
        mock_instance._meta.verbose_name = "Mock Model"
        
        node = DataNode(mock_instance, descriptive_name="Desc Name")
        self.assertEqual(node.name, "Mock Model")
        self.assertEqual(node.descriptive_name, "Desc Name")

    def test_find_unambiguous_names(self):
        """
        Test that find_unambiguous_names resolves name conflicts among siblings.
        """
        root = DataNode("root")
        
        # Create 3 children with same name
        child1 = DataNode("child")
        child2 = DataNode("child")
        child3 = DataNode("child")
        
        root.children = [child1, child2, child3]
        
        # recursion_offset=1 means start renaming at level 1 (children)
        # The logic:
        # process_index = names[:i].count(child.name) + 1
        # if process_index > 1: child.name += " #2", etc.
        
        # renaming_offset=0 means start renaming at this level (immediate children)
        root.find_unambiguous_names(renaming_offset=0)
        
        self.assertEqual(child1.name, "child")
        self.assertEqual(child2.name, "child #2") # Note the non-breaking space likely used in source
        self.assertEqual(child3.name, "child #3")

    def test_find_unambiguous_names_with_parent_prefix(self):
        """
        Test that when renaming_offset < 0, parent name is prepended.
        """
        root = DataNode("Parent")
        child = DataNode("Child")
        root.children = [child]
        
        # renaming_offset < 0 -> prepend parent name
        root.find_unambiguous_names(renaming_offset=-1)
        
        self.assertEqual(child.name, "Parent, Child")
