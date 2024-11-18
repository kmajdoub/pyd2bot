import sys
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class TreePrinter:
    """
    A utility class for pretty-printing tree structures with various formatting options.
    """
    
    # Define ASCII vs Unicode characters based on platform
    if sys.platform == 'win32':
        CHARS = {
            'corner': '\\--',
            'tee': '+--',
            'vertical': '|  ',
            'space': '   '
        }
    else:
        CHARS = {
            'corner': '└── ',
            'tee': '├── ',
            'vertical': '│   ',
            'space': '    '
        }
        
    @staticmethod
    def get_ascii_tree(node, prefix="", is_last=True, include_root=True):
        """
        Returns a string representation of the tree using ASCII characters.
        
        Args:
            node: The node to print (must have children attribute and a __str__ method)
            prefix (str): Current prefix for line (used in recursion)
            is_last (bool): Is this the last child of its parent?
            include_root (bool): Whether to include the root node in the output
            
        Returns:
            str: ASCII representation of the tree
        """
        result = []
        
        # Add current node
        if not include_root and prefix == "":
            pass  # Skip root
        else:
            node_char = TreePrinter.CHARS['corner'] if is_last else TreePrinter.CHARS['tee']
            result.append(f"{prefix}{node_char}{type(node).__name__}")
        
        # Prepare prefix for children
        child_prefix = prefix + (TreePrinter.CHARS['space'] if is_last else TreePrinter.CHARS['vertical'])
        
        # Process children
        if hasattr(node, 'children'):
            children = node.children
            for i, child in enumerate(children):
                if child == node:
                    Logger().error(f"node {type(node).__name__} is it self child")
                    continue
                is_last_child = i == len(children) - 1
                result.append(TreePrinter.get_ascii_tree(
                    child,
                    child_prefix,
                    is_last_child,
                    include_root=True
                ))
        
        return "\n".join(result)
    
    @staticmethod
    def get_compact_tree(node, level=0, include_root=True):
        """
        Returns a compact string representation of the tree using simple indentation.
        
        Args:
            node: The node to print (must have children attribute)
            level (int): Current indentation level
            include_root (bool): Whether to include the root node in the output
            
        Returns:
            str: Compact representation of the tree
        """
        result = []
        indent = "  " * level
        
        # Add current node
        if not (level == 0 and not include_root):
            result.append(f"{indent}{type(node).__name__}")
        
        # Process children
        if hasattr(node, 'children'):
            for child in node.children:
                result.append(TreePrinter.get_compact_tree(
                    child,
                    level + 1,
                    include_root=True
                ))
                
        return "\n".join(result)
    
    @staticmethod
    def get_detailed_tree(node, level=0, include_root=True, show_attributes=False):
        """
        Returns a detailed string representation of the tree including node attributes.
        
        Args:
            node: The node to print (must have children attribute)
            level (int): Current indentation level
            include_root (bool): Whether to include the root node in the output
            show_attributes (bool): Whether to show node attributes
            
        Returns:
            str: Detailed representation of the tree
        """
        result = []
        indent = "  " * level
        
        # Add current node with attributes
        if not (level == 0 and not include_root):
            node_str = type(node).__name__
            if show_attributes:
                attrs = {k: v for k, v in vars(node).items() 
                        if not k.startswith('_') and k != 'children'}
                if attrs:
                    node_str += f" {attrs}"
            result.append(f"{indent}{node_str}")
        
        # Process children
        if hasattr(node, 'children'):
            for child in node.children:
                result.append(TreePrinter.get_detailed_tree(
                    child,
                    level + 1,
                    include_root=True,
                    show_attributes=show_attributes
                ))
                
        return "\n".join(result)

# Example usage:
"""
# Assuming your tree node class looks something like this:
class Node:
    def __init__(self):
        self.children = []
        
    def getTreeStr(self, level=0):
        # Replace your current method with:
        return TreePrinter.get_ascii_tree(self)
        
        # Or for more options:
        # return TreePrinter.get_compact_tree(self)
        # return TreePrinter.get_detailed_tree(self, show_attributes=True)
"""