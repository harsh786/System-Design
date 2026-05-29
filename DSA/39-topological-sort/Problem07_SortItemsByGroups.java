import java.util.*;

/**
 * Problem: Sort Items by Groups Respecting Dependencies
 * Sort items considering both group and item dependencies.
 *
 * Approach: Two-level topological sort - sort groups, then items within groups
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Ordering microservice deployments where services belong to teams
 * and both inter-team and intra-team dependencies must be respected.
 */
public class Problem07_SortItemsByGroups {

    public int[] sortItems(int n, int m, int[] group, List<List<Integer>> beforeItems) {
        // Assign unique group ids to ungrouped items
        int groupId = m;
        for (int i = 0; i < n; i++)
            if (group[i] == -1) group[i] = groupId++;

        List<List<Integer>> groupGraph = new ArrayList<>(), itemGraph = new ArrayList<>();
        int[] groupInDeg = new int[groupId], itemInDeg = new int[n];
        for (int i = 0; i < groupId; i++) groupGraph.add(new ArrayList<>());
        for (int i = 0; i < n; i++) itemGraph.add(new ArrayList<>());

        for (int i = 0; i < n; i++) {
            for (int prev : beforeItems.get(i)) {
                itemGraph.get(prev).add(i);
                itemInDeg[i]++;
                if (group[prev] != group[i]) {
                    groupGraph.get(group[prev]).add(group[i]);
                    groupInDeg[group[i]]++;
                }
            }
        }

        List<Integer> groupOrder = topoSort(groupGraph, groupInDeg, groupId);
        List<Integer> itemOrder = topoSort(itemGraph, itemInDeg, n);
        if (groupOrder.isEmpty() || itemOrder.isEmpty()) return new int[0];

        Map<Integer, List<Integer>> groupItems = new HashMap<>();
        for (int item : itemOrder)
            groupItems.computeIfAbsent(group[item], k -> new ArrayList<>()).add(item);

        int[] result = new int[n];
        int idx = 0;
        for (int g : groupOrder)
            for (int item : groupItems.getOrDefault(g, Collections.emptyList()))
                result[idx++] = item;
        return result;
    }

    private List<Integer> topoSort(List<List<Integer>> graph, int[] inDeg, int count) {
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < count; i++) if (inDeg[i] == 0) q.offer(i);
        List<Integer> order = new ArrayList<>();
        while (!q.isEmpty()) {
            int node = q.poll();
            order.add(node);
            for (int nei : graph.get(node)) if (--inDeg[nei] == 0) q.offer(nei);
        }
        return order.size() == count ? order : Collections.emptyList();
    }

    public static void main(String[] args) {
        Problem07_SortItemsByGroups solver = new Problem07_SortItemsByGroups();
        List<List<Integer>> before = Arrays.asList(
            Collections.emptyList(), Arrays.asList(6), Arrays.asList(5),
            Arrays.asList(6), Collections.emptyList(), Collections.emptyList(),
            Collections.emptyList(), Collections.emptyList()
        );
        System.out.println(Arrays.toString(solver.sortItems(8, 2, new int[]{-1,-1,1,0,0,1,0,-1}, before)));
    }
}
