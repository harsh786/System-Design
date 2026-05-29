import java.util.*;

/**
 * Problem: Word Ladder II
 * Find all shortest transformation sequences.
 *
 * Approach: BFS to find shortest distance, then DFS backtracking to find all paths
 *
 * Time Complexity: O(N * M * 26 + paths)
 * Space Complexity: O(N * M)
 *
 * Production Analogy: Finding all equally optimal migration paths for comparison.
 */
public class Problem33_WordLadderII {

    public List<List<String>> findLadders(String beginWord, String endWord, List<String> wordList) {
        Set<String> wordSet = new HashSet<>(wordList);
        if (!wordSet.contains(endWord)) return new ArrayList<>();

        Map<String, Integer> dist = new HashMap<>();
        dist.put(beginWord, 0);
        Queue<String> q = new LinkedList<>();
        q.offer(beginWord);

        while (!q.isEmpty()) {
            String word = q.poll();
            char[] arr = word.toCharArray();
            for (int i = 0; i < arr.length; i++) {
                char orig = arr[i];
                for (char c = 'a'; c <= 'z'; c++) {
                    arr[i] = c;
                    String next = new String(arr);
                    if (wordSet.contains(next) && !dist.containsKey(next)) {
                        dist.put(next, dist.get(word) + 1);
                        q.offer(next);
                    }
                }
                arr[i] = orig;
            }
        }

        List<List<String>> result = new ArrayList<>();
        if (!dist.containsKey(endWord)) return result;
        dfs(endWord, beginWord, dist, new ArrayList<>(Arrays.asList(endWord)), result, wordSet);
        return result;
    }

    private void dfs(String word, String begin, Map<String, Integer> dist, List<String> path, List<List<String>> result, Set<String> wordSet) {
        if (word.equals(begin)) { List<String> copy = new ArrayList<>(path); Collections.reverse(copy); result.add(copy); return; }
        char[] arr = word.toCharArray();
        for (int i = 0; i < arr.length; i++) {
            char orig = arr[i];
            for (char c = 'a'; c <= 'z'; c++) {
                arr[i] = c;
                String prev = new String(arr);
                if (dist.containsKey(prev) && dist.get(prev) == dist.get(word) - 1) {
                    path.add(prev); dfs(prev, begin, dist, path, result, wordSet); path.remove(path.size()-1);
                }
            }
            arr[i] = orig;
        }
    }

    public static void main(String[] args) {
        Problem33_WordLadderII solver = new Problem33_WordLadderII();
        System.out.println(solver.findLadders("hit", "cog", Arrays.asList("hot","dot","dog","lot","log","cog")));
    }
}
