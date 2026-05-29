import java.util.*;

public class Problem15_WordLadder {
    public static int ladderLength(String beginWord, String endWord, List<String> wordList) {
        Set<String> dict = new HashSet<>(wordList);
        if (!dict.contains(endWord)) return 0;
        Queue<String> q = new LinkedList<>();
        q.offer(beginWord); int level = 1;
        while (!q.isEmpty()) {
            level++;
            for (int sz = q.size(); sz > 0; sz--) {
                char[] cur = q.poll().toCharArray();
                for (int i = 0; i < cur.length; i++) {
                    char orig = cur[i];
                    for (char c = 'a'; c <= 'z'; c++) {
                        cur[i] = c;
                        String next = new String(cur);
                        if (next.equals(endWord)) return level;
                        if (dict.remove(next)) q.offer(next);
                    }
                    cur[i] = orig;
                }
            }
        }
        return 0;
    }
    public static void main(String[] args) {
        System.out.println(ladderLength("hit", "cog", Arrays.asList("hot","dot","dog","lot","log","cog"))); // 5
    }
}
