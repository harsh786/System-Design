import java.util.*;

/**
 * Problem: Minimum Genetic Mutation (LeetCode 433)
 * Approach: BFS - genes are nodes, edges connect genes differing by one char
 * Time: O(B*M*4) B=bank size, M=gene length, Space: O(B)
 * Production Analogy: Finding minimum schema migration steps between database versions
 */
public class Problem10_MinimumGeneticMutation {
    public int minMutation(String startGene, String endGene, String[] bank) {
        Set<String> bankSet = new HashSet<>(Arrays.asList(bank));
        if (!bankSet.contains(endGene)) return -1;
        char[] genes = {'A','C','G','T'};
        Queue<String> q = new LinkedList<>();
        q.offer(startGene);
        Set<String> visited = new HashSet<>();
        visited.add(startGene);
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                char[] curr = q.poll().toCharArray();
                for (int j = 0; j < 8; j++) {
                    char orig = curr[j];
                    for (char g : genes) {
                        curr[j] = g;
                        String next = new String(curr);
                        if (next.equals(endGene)) return steps + 1;
                        if (bankSet.contains(next) && !visited.contains(next)) {
                            visited.add(next); q.offer(next);
                        }
                    }
                    curr[j] = orig;
                }
            }
            steps++;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(new Problem10_MinimumGeneticMutation().minMutation(
            "AACCGGTT", "AAACGGTA", new String[]{"AACCGGTA","AACCGCTA","AAACGGTA"})); // 2
    }
}
