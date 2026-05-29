import java.util.*;

/**
 * Problem: Sequence Reconstruction
 * Check if original sequence can be uniquely reconstructed from subsequences.
 *
 * Approach: Topological sort - unique if queue never has more than 1 element
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Verifying event ordering is deterministic from partial logs.
 */
public class Problem06_SequenceReconstruction {

    public boolean sequenceReconstruction(int[] org, List<List<Integer>> seqs) {
        Map<Integer, Set<Integer>> graph = new HashMap<>();
        Map<Integer, Integer> inDegree = new HashMap<>();

        for (List<Integer> seq : seqs) {
            for (int num : seq) {
                graph.putIfAbsent(num, new HashSet<>());
                inDegree.putIfAbsent(num, 0);
            }
            for (int i = 0; i < seq.size() - 1; i++) {
                if (graph.get(seq.get(i)).add(seq.get(i + 1)))
                    inDegree.merge(seq.get(i + 1), 1, Integer::sum);
            }
        }

        if (inDegree.size() != org.length) return false;

        Queue<Integer> queue = new LinkedList<>();
        for (var e : inDegree.entrySet())
            if (e.getValue() == 0) queue.offer(e.getKey());

        int idx = 0;
        while (!queue.isEmpty()) {
            if (queue.size() > 1) return false;
            int node = queue.poll();
            if (idx >= org.length || node != org[idx++]) return false;
            for (int nei : graph.get(node))
                if (inDegree.merge(nei, -1, Integer::sum) == 0) queue.offer(nei);
        }
        return idx == org.length;
    }

    public static void main(String[] args) {
        Problem06_SequenceReconstruction solver = new Problem06_SequenceReconstruction();
        List<List<Integer>> seqs = Arrays.asList(Arrays.asList(1,2), Arrays.asList(1,3), Arrays.asList(2,3));
        System.out.println(solver.sequenceReconstruction(new int[]{1,2,3}, seqs)); // true
    }
}
