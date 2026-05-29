import java.util.*;

public class Problem13_LazyGraphTraversalIterator implements Iterator<Integer> {
    Map<Integer, List<Integer>> graph;
    Set<Integer> visited = new HashSet<>();
    Deque<Integer> stack = new ArrayDeque<>();

    public Problem13_LazyGraphTraversalIterator(Map<Integer, List<Integer>> graph, int start) {
        this.graph = graph; stack.push(start); visited.add(start);
    }

    public boolean hasNext() { return !stack.isEmpty(); }

    public Integer next() {
        int node = stack.pop();
        for (int neighbor : graph.getOrDefault(node, Collections.emptyList()))
            if (visited.add(neighbor)) stack.push(neighbor);
        return node;
    }

    public static void main(String[] args) {
        Map<Integer, List<Integer>> g = new HashMap<>();
        g.put(0, Arrays.asList(1,2)); g.put(1, Arrays.asList(3));
        g.put(2, Arrays.asList(3,4)); g.put(3, Arrays.asList()); g.put(4, Arrays.asList());
        Problem13_LazyGraphTraversalIterator it = new Problem13_LazyGraphTraversalIterator(g, 0);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
