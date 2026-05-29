import java.util.*;

public class Problem43_GraphBFSIterator implements Iterator<Integer> {
    Queue<Integer> queue = new LinkedList<>();
    Set<Integer> visited = new HashSet<>();
    Map<Integer, List<Integer>> graph;

    public Problem43_GraphBFSIterator(Map<Integer, List<Integer>> graph, int start) {
        this.graph = graph; queue.offer(start); visited.add(start);
    }

    public boolean hasNext() { return !queue.isEmpty(); }

    public Integer next() {
        int node = queue.poll();
        for (int n : graph.getOrDefault(node, Collections.emptyList()))
            if (visited.add(n)) queue.offer(n);
        return node;
    }

    public static void main(String[] args) {
        Map<Integer, List<Integer>> g = new HashMap<>();
        g.put(0, Arrays.asList(1,2)); g.put(1, Arrays.asList(3)); g.put(2, Arrays.asList(3,4));
        g.put(3, Arrays.asList()); g.put(4, Arrays.asList());
        Problem43_GraphBFSIterator it = new Problem43_GraphBFSIterator(g, 0);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 0 1 2 3 4
    }
}
