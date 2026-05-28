/**
 * Problem 46: Rearrange String k Distance Apart (LeetCode 358)
 *
 * Greedy Choice: Always place the most frequent available character. Use cooldown queue.
 *
 * Time: O(n log 26) = O(n), Space: O(n)
 *
 * Production Analogy: Scheduling API calls with minimum k-interval between same endpoint hits.
 */
import java.util.*;
public class Problem46_RearrangeStringKDistanceApart {
    
    public static String rearrangeString(String s, int k) {
        if (k <= 1) return s;
        int[] freq = new int[26];
        for (char c : s.toCharArray()) freq[c - 'a']++;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> b[1] - a[1]);
        for (int i = 0; i < 26; i++) if (freq[i] > 0) pq.offer(new int[]{i, freq[i]});
        Queue<int[]> cooldown = new LinkedList<>();
        StringBuilder sb = new StringBuilder();
        while (!pq.isEmpty() || !cooldown.isEmpty()) {
            if (!cooldown.isEmpty() && sb.length() - cooldown.peek()[2] >= k) {
                int[] ready = cooldown.poll();
                pq.offer(new int[]{ready[0], ready[1]});
            }
            if (pq.isEmpty()) return "";
            int[] curr = pq.poll();
            sb.append((char)('a' + curr[0]));
            if (curr[1] - 1 > 0)
                cooldown.offer(new int[]{curr[0], curr[1] - 1, sb.length() - 1});
        }
        return sb.length() == s.length() ? sb.toString() : "";
    }
    
    public static void main(String[] args) {
        System.out.println(rearrangeString("aabbcc", 3)); // "abcabc"
        System.out.println(rearrangeString("aaabc", 3));  // "" (impossible)
        System.out.println(rearrangeString("aaadbbcc", 2)); // "abacabcd" or similar
    }
}
