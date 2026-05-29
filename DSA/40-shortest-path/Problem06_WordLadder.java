import java.util.*;

/**
 * Problem: Word Ladder
 * Find shortest transformation sequence from beginWord to endWord.
 *
 * Approach: BFS with wildcard pattern matching for neighbor finding
 *
 * Time Complexity: O(M^2 * N) where M=word length, N=word list size
 * Space Complexity: O(M^2 * N)
 *
 * Production Analogy: Finding minimum config changes to migrate between system states.
 */
public class Problem06_WordLadder {

    public int ladderLength(String beginWord, String endWord, List<String> wordList) {
        Set<String> wordSet = new HashSet<>(wordList);
        if (!wordSet.contains(endWord)) return 0;

        Queue<String> q = new LinkedList<>();
        q.offer(beginWord);
        int level = 1;

        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                char[] word = q.poll().toCharArray();
                for (int j = 0; j < word.length; j++) {
                    char orig = word[j];
                    for (char c = 'a'; c <= 'z'; c++) {
                        word[j] = c;
                        String next = new String(word);
                        if (next.equals(endWord)) return level + 1;
                        if (wordSet.remove(next)) q.offer(next);
                    }
                    word[j] = orig;
                }
            }
            level++;
        }
        return 0;
    }

    public static void main(String[] args) {
        Problem06_WordLadder solver = new Problem06_WordLadder();
        System.out.println(solver.ladderLength("hit", "cog", Arrays.asList("hot","dot","dog","lot","log","cog"))); // 5
    }
}
