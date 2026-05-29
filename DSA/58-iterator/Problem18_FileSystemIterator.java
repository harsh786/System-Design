import java.util.*;

public class Problem18_FileSystemIterator implements Iterator<String> {
    // DFS iteration over simulated file system
    static class FSNode { String name; boolean isDir; List<FSNode> children = new ArrayList<>();
        FSNode(String n, boolean d){name=n;isDir=d;}
    }

    Deque<Object[]> stack = new ArrayDeque<>(); // [FSNode, path]

    public Problem18_FileSystemIterator(FSNode root) { stack.push(new Object[]{root, ""}); }

    public boolean hasNext() { return !stack.isEmpty(); }

    public String next() {
        Object[] top = stack.pop();
        FSNode node = (FSNode) top[0];
        String path = top[1] + "/" + node.name;
        if (node.isDir) for (int i = node.children.size()-1; i >= 0; i--)
            stack.push(new Object[]{node.children.get(i), path});
        return path;
    }

    public static void main(String[] args) {
        FSNode root = new FSNode("root", true);
        FSNode src = new FSNode("src", true); src.children.add(new FSNode("main.java", false));
        root.children.add(src); root.children.add(new FSNode("README.md", false));
        Problem18_FileSystemIterator it = new Problem18_FileSystemIterator(root);
        while (it.hasNext()) System.out.println(it.next());
    }
}
