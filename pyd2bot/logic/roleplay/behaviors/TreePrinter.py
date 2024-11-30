import sys
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class TreePrinter:
    CHARS = {
        'corner': '\\--',
        'tee': '+--',
        'vertical': '|  ',
        'space': '   '
    }
        
    @staticmethod
    def get_ascii_tree(node, prefix="", is_last=True, include_root=True, visited=None):
        """
        Returns a string representation of the tree using ASCII characters.
        
        Args:
            node: The node to print (must have children attribute and a __str__ method)
            prefix (str): Current prefix for line (used in recursion)
            is_last (bool): Is this the last child of its parent?
            include_root (bool): Whether to include the root node in the output
            visited (set): Set of visited node ids to detect cycles
            
        Returns:
            str: ASCII representation of the tree
        """
        if visited is None:
            visited = set()
            
        node_id = id(node)
        result = []
        
        # Check for cycles
        if node_id in visited:
            return f"{prefix}{TreePrinter.CHARS['corner']}[CYCLE] {type(node).__name__}"
            
        visited.add(node_id)
        
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
                    Logger().error(f"node {type(node).__name__} is its own child")
                    continue
                is_last_child = i == len(children) - 1
                result.append(TreePrinter.get_ascii_tree(
                    child,
                    child_prefix,
                    is_last_child,
                    include_root=True,
                    visited=visited.copy()  # Pass a copy to avoid affecting sibling traversal
                ))
        
        return "\n".join(result)
    
    @staticmethod
    def get_compact_tree(node, level=0, include_root=True, visited=None):
        """
        Returns a compact string representation of the tree using simple indentation.
        """
        if visited is None:
            visited = set()
            
        node_id = id(node)
        if node_id in visited:
            return f"{'  ' * level}[CYCLE] {type(node).__name__}"
            
        visited.add(node_id)
        result = []
        indent = "  " * level
        
        if not (level == 0 and not include_root):
            result.append(f"{indent}{type(node).__name__}")
        
        if hasattr(node, 'children'):
            for child in node.children:
                result.append(TreePrinter.get_compact_tree(
                    child,
                    level + 1,
                    include_root=True,
                    visited=visited.copy()
                ))
                
        return "\n".join(result)
    
    @staticmethod
    def get_detailed_tree(node, level=0, include_root=True, show_attributes=False, visited=None):
        """
        Returns a detailed string representation of the tree including node attributes.
        """
        if visited is None:
            visited = set()
            
        node_id = id(node)
        if node_id in visited:
            return f"{'  ' * level}[CYCLE] {type(node).__name__}"
            
        visited.add(node_id)
        result = []
        indent = "  " * level
        
        if not (level == 0 and not include_root):
            node_str = type(node).__name__
            if show_attributes:
                attrs = {k: v for k, v in vars(node).items() 
                        if not k.startswith('_') and k != 'children'}
                if attrs:
                    node_str += f" {attrs}"
            result.append(f"{indent}{node_str}")
        
        if hasattr(node, 'children'):
            for child in node.children:
                result.append(TreePrinter.get_detailed_tree(
                    child,
                    level + 1,
                    include_root=True,
                    show_attributes=show_attributes,
                    visited=visited.copy()
                ))
                
        return "\n".join(result)
