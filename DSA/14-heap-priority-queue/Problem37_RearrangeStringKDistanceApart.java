import java.util.*;

/**
 * Problem 37: Rearrange String k Distance Apart (LeetCode 358)
 * 
 * Approach: Max-heap by frequency + cooldown queue of size k.
 * 
 * Time Complexity: O(N log 26) = O(N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Rate limiting - ensuring the same API key isn't used more
 * than once within K time slots apart.
 */
public class Problem37_RearrangeStringKDistanceApart {
    
    public String rearrangeString(String s, int k) {
        if (k <= 1) return s;
        int[] freq = new int[26];
        for (char c : s.toCharArray()) freq[c - 'a']++;
        
        PriorityQueue<int[]> maxHeap = new PriorityQueue<>((a, b) -> b[1] - a[1]);
        for (int i = 0; i < 26; i++) if (freq[i] > 0) maxHeap.offer(new int[]{i, freq[i]});
        
        Queue<int[]> cooldown = new LinkedList<>();
        StringBuilder sb = new StringBuilder();
        
        while (!maxHeap.isEmpty() || !cooldown.isEmpty()) {
            if (!cooldown.isEmpty() && sb.length() - cooldown.peek()[2] >= k) {
                int[] ready = cooldown.poll();
                maxHeap.offer(new int[]{ready[0], ready[1]});
            }
            if (maxHeap.isEmpty()) return "";
            int[] curr = maxHeap.poll();
            sb.append((char)(curr[0] + 'a'));
            if (curr[1] - 1 > 0) cooldown.offer(new int[]{curr[0], curr[1] - 1, sb.length() - 1});
        }
        return sb.length() == s.length() ? sb.toString() : "";
    }
    
    public static void main(String[] args) {
        Problem37_RearrangeStringKDistanceApart sol = new Problem37_RearrangeStringKDistanceApart();
        System.out.println(sol.rearrangeString("aabbcc", 3)); // "abcabc"
        System.out.println(sol.rearrangeString("aaabc", 3));  // "" (impossible)
        System.out.println(sol.rearrangeString("aaadbbcc", 2)); // "abacabcd" or similar
    }
}
