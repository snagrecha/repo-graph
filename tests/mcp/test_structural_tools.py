import pytest
from codenexus.graph.schema import Node, NodeType
from codenexus.mcp.tools import structural

def test_search_nodes_mcp(tmp_store):
    node = Node(
        id="test-id",
        type=NodeType.FUNCTION,
        name="my_func",
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        language="python",
        metadata={}
    )
    tmp_store.add_node(node)
    
    results = structural.search_nodes(tmp_store, query="my_func")
    assert len(results) == 1
    assert results[0]["name"] == "my_func"
    assert results[0]["type"] == "function"

def test_get_node_signature_mcp(tmp_store, tmp_path):
    # Create a dummy file
    repo_root = tmp_path
    src_file = repo_root / "src" / "main.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("def my_func():\n    return 42\n")
    
    node = Node(
        id="test-id",
        type=NodeType.FUNCTION,
        name="my_func",
        file_path="src/main.py",
        start_line=1,
        end_line=2,
        language="python",
        metadata={}
    )
    tmp_store.add_node(node)
    
    result = structural.get_node_signature(tmp_store, str(repo_root), "test-id")
    assert result is not None
    assert "def my_func():" in result["signature_snippet"]
    assert "return 42" in result["signature_snippet"]
