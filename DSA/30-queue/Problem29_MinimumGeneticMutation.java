import java.util.*;

public class Problem29_MinimumGeneticMutation {
    public static int minMutation(String start, String end, String[] bank) {
        Set<String> dict = new HashSet<>(Arrays.asList(bank));
        if (!dict.contains(end)) return -1;
        Queue<String> q = new LinkedList<>();
        q.offer(start); int level = 0;
        char[] genes = {'A','C','G','T'};
        while (!q.isEmpty()) {
            level++;
            for (int sz = q.size(); sz > 0; sz--) {
                char[] cur = q.poll().toCharArray();
                for (int i = 0; i < cur.length; i++) {
                    char orig = cur[i];
                    for (char g : genes) {
                        cur[i] = g;
                        String next = new String(cur);
                        if (next.equals(end)) return level;
                        if (dict.remove(next)) q.offer(next);
                    }
                    cur[i] = orig;
                }
            }
        }
        return -1;
    }
    public static void main(String[] args) {
        System.out.println(minMutation("AACCGGTT", "AAACGGTA", new String[]{"AACCGGTA","AACCGCTA","AAACGGTA"})); // 2
    }
}
