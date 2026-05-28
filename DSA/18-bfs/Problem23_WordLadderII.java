import java.util.*;

/**
 * Problem: Word Ladder II (LeetCode 126)
 * Approach: BFS to build shortest path DAG, then DFS backtrack to collect all paths
 * Time: O(N*M*26 + paths), Space: O(N*M)
 * Production Analogy: Finding all equally-optimal migration paths between system versions
 */
public class Problem23_WordLadderII {
    public List<List<String>> findLadders(String beginWord, String endWord, List<String> wordList) {
        Set<String> wordSet = new HashSet<>(wordList);
        List<List<String>> res = new ArrayList<>();
        if (!wordSet.contains(endWord)) return res;
        Map<String, List<String>> parents = new HashMap<>();
        Set<String> currentLevel = new HashSet<>(), nextLevel = new HashSet<>();
        currentLevel.add(beginWord);
        boolean found = false;
        while (!currentLevel.isEmpty() && !found) {
            wordSet.removeAll(currentLevel);
            for (String word : currentLevel) {
                char[] arr = word.toCharArray();
                for (int i = 0; i < arr.length; i++) {
                    char orig = arr[i];
                    for (char c = 'a'; c <= 'z'; c++) {
                        arr[i] = c;
                        String next = new String(arr);
                        if (wordSet.contains(next)) {
                            nextLevel.add(next);
                            parents.computeIfAbsent(next, k -> new ArrayList<>()).add(word);
                            if (next.equals(endWord)) found = true;
                        }
                    }
                    arr[i] = orig;
                }
            }
            currentLevel = nextLevel; nextLevel = new HashSet<>();
        }
        if (found) backtrack(endWord, beginWord, parents, new LinkedList<>(Arrays.asList(endWord)), res);
        return res;
    }

    private void backtrack(String word, String begin, Map<String, List<String>> parents, LinkedList<String> path, List<List<String>> res) {
        if (word.equals(begin)) { res.add(new ArrayList<>(path)); return; }
        for (String p : parents.getOrDefault(word, Collections.emptyList())) {
            path.addFirst(p);
            backtrack(p, begin, parents, path, res);
            path.removeFirst();
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem23_WordLadderII().findLadders("hit", "cog",
            Arrays.asList("hot","dot","dog","lot","log","cog")));
    }
}
