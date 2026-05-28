import java.util.*;

/**
 * Problem 17: Word Ladder (LeetCode 127)
 * 
 * Approach: BFS level-by-level. Each word is a node; edges connect words differing by 1 char.
 * Time: O(M^2 * N) where M=word length, N=word list size, Space: O(M*N)
 * 
 * Production Analogy: Finding minimum config changes to migrate from one system state to another.
 */
public class Problem17_WordLadder {
    
    public int ladderLength(String beginWord, String endWord, List<String> wordList) {
        Set<String> dict = new HashSet<>(wordList);
        if (!dict.contains(endWord)) return 0;
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
                        if (c == orig) continue;
                        word[j] = c;
                        String next = new String(word);
                        if (next.equals(endWord)) return level + 1;
                        if (dict.remove(next)) q.offer(next);
                    }
                    word[j] = orig;
                }
            }
            level++;
        }
        return 0;
    }
    
    public static void main(String[] args) {
        Problem17_WordLadder sol = new Problem17_WordLadder();
        System.out.println(sol.ladderLength("hit","cog",Arrays.asList("hot","dot","dog","lot","log","cog"))); // 5
        System.out.println(sol.ladderLength("hit","cog",Arrays.asList("hot","dot","dog","lot","log"))); // 0
    }
}
