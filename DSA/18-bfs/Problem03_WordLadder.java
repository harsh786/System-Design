import java.util.*;

/**
 * Problem: Word Ladder (LeetCode 127)
 * Approach: BFS - each word is a node, edges connect words differing by one char
 * Time: O(M^2 * N) M=word length, N=word list size, Space: O(M*N)
 * Production Analogy: Finding minimum hops for version migration between compatible releases
 */
public class Problem03_WordLadder {
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
                        if (wordSet.contains(next)) { q.offer(next); wordSet.remove(next); }
                    }
                    word[j] = orig;
                }
            }
            level++;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(new Problem03_WordLadder().ladderLength("hit", "cog",
            Arrays.asList("hot","dot","dog","lot","log","cog"))); // 5
    }
}
