import java.util.*;

public class Problem19_DirectoryTreeIterator implements Iterator<String> {
    Deque<String[]> stack = new ArrayDeque<>(); // [path, indent]
    Map<String, List<String>> tree; // dir -> children

    public Problem19_DirectoryTreeIterator(Map<String, List<String>> tree, String root) {
        this.tree = tree; stack.push(new String[]{root, ""});
    }

    public boolean hasNext() { return !stack.isEmpty(); }

    public String next() {
        String[] top = stack.pop();
        String path = top[0], indent = top[1];
        List<String> children = tree.getOrDefault(path, Collections.emptyList());
        for (int i = children.size()-1; i >= 0; i--)
            stack.push(new String[]{children.get(i), indent + "  "});
        return indent + path;
    }

    public static void main(String[] args) {
        Map<String, List<String>> tree = new HashMap<>();
        tree.put("/", Arrays.asList("src", "docs", "README"));
        tree.put("src", Arrays.asList("main.java", "util.java"));
        tree.put("docs", Arrays.asList("guide.md"));
        Problem19_DirectoryTreeIterator it = new Problem19_DirectoryTreeIterator(tree, "/");
        while (it.hasNext()) System.out.println(it.next());
    }
}
