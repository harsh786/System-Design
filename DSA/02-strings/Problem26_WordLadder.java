import java.util.*;

/**
 * Problem 26: Word Ladder (LeetCode 127)
 * 
 * Approach: BFS. Each word is a node, edges connect words differing by one char.
 * O(M^2 * N) time where M=word length, N=wordList size. O(M*N) space.
 * 
 * Production Analogy: Like finding the shortest migration path between database schemas
 * where each step changes only one column.
 */
public class Problem26_WordLadder {

    public static int ladderLength(String beginWord, String endWord, List<String> wordList) {
        Set<String> wordSet = new HashSet<>(wordList);
        if (!wordSet.contains(endWord)) return 0;
        Queue<String> queue = new LinkedList<>();
        queue.offer(beginWord);
        int level = 1;
        while (!queue.isEmpty()) {
            int size = queue.size();
            for (int i = 0; i < size; i++) {
                char[] word = queue.poll().toCharArray();
                for (int j = 0; j < word.length; j++) {
                    char orig = word[j];
                    for (char c = 'a'; c <= 'z'; c++) {
                        if (c == orig) continue;
                        word[j] = c;
                        String next = new String(word);
                        if (next.equals(endWord)) return level + 1;
                        if (wordSet.remove(next)) queue.offer(next);
                    }
                    word[j] = orig;
                }
            }
            level++;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(ladderLength("hit", "cog", 
            Arrays.asList("hot","dot","dog","lot","log","cog"))); // 5
        System.out.println(ladderLength("hit", "cog", 
            Arrays.asList("hot","dot","dog","lot","log"))); // 0
    }
}
