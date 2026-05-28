import java.util.*;

/**
 * Problem: Bidirectional BFS Word Ladder
 * Approach: BFS from both ends, expand smaller frontier, meet in middle
 * Time: O(M*26*N) but much faster in practice, Space: O(N)
 * Production Analogy: Bidirectional service discovery from source and destination simultaneously
 */
public class Problem43_BidirectionalBFSWordLadder {
    public int ladderLength(String beginWord, String endWord, List<String> wordList) {
        Set<String> wordSet = new HashSet<>(wordList);
        if (!wordSet.contains(endWord)) return 0;
        Set<String> front = new HashSet<>(), back = new HashSet<>(), visited = new HashSet<>();
        front.add(beginWord); back.add(endWord);
        visited.add(beginWord); visited.add(endWord);
        int level = 1;
        while (!front.isEmpty() && !back.isEmpty()) {
            if (front.size() > back.size()) { Set<String> tmp = front; front = back; back = tmp; }
            Set<String> nextFront = new HashSet<>();
            for (String word : front) {
                char[] arr = word.toCharArray();
                for (int i = 0; i < arr.length; i++) {
                    char orig = arr[i];
                    for (char c = 'a'; c <= 'z'; c++) {
                        arr[i] = c;
                        String next = new String(arr);
                        if (back.contains(next)) return level + 1;
                        if (wordSet.contains(next) && !visited.contains(next)) {
                            visited.add(next); nextFront.add(next);
                        }
                    }
                    arr[i] = orig;
                }
            }
            front = nextFront; level++;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(new Problem43_BidirectionalBFSWordLadder().ladderLength("hit", "cog",
            Arrays.asList("hot","dot","dog","lot","log","cog"))); // 5
    }
}
