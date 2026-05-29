import java.util.*;

public class Problem44_GraphDFSIterator implements Iterator<Integer> {
    Deque<Integer> stack = new ArrayDeque<>();
    Set<Integer> visited = new HashSet<>();
    Map<Integer, List<Integer>> graph;

    public Problem44_GraphDFSIterator(Map<Integer, List<Integer>> graph, int start) {
        this.graph = graph; stack.push(start); visited.add(start);
    }

    public boolean hasNext() { return !stack.isEmpty(); }

    public Integer next() {
        int node = stack.pop();
        for (int n : graph.getOrDefault(node, Collections.emptyList()))
            if (visited.add(n)) stack.push(n);
        return node;
    }

    public static void main(String[] args) {
        Map<Integer, List<Integer>> g = new HashMap<>();
        g.put(0, Arrays.asList(1,2)); g.put(1, Arrays.asList(3)); g.put(2, Arrays.asList(4));
        g.put(3, Arrays.asList()); g.put(4, Arrays.asList());
        Problem44_GraphDFSIterator it = new Problem44_GraphDFSIterator(g, 0);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
