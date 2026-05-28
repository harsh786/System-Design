import java.util.*;

/**
 * Problem 7: Reorganize String (LeetCode 767)
 * 
 * Approach: Max-heap by frequency. Greedily place most frequent char, then swap.
 * 
 * Time Complexity: O(N log 26) = O(N)
 * Space Complexity: O(26) = O(1)
 * 
 * Production Analogy: Load balancing requests across servers ensuring no single
 * server gets consecutive requests (preventing hotspots).
 */
public class Problem07_ReorganizeString {
    
    public String reorganizeString(String s) {
        int[] freq = new int[26];
        for (char c : s.toCharArray()) freq[c - 'a']++;
        
        PriorityQueue<int[]> maxHeap = new PriorityQueue<>((a, b) -> b[1] - a[1]);
        for (int i = 0; i < 26; i++) if (freq[i] > 0) maxHeap.offer(new int[]{i, freq[i]});
        
        StringBuilder sb = new StringBuilder();
        while (maxHeap.size() >= 2) {
            int[] first = maxHeap.poll();
            int[] second = maxHeap.poll();
            sb.append((char)(first[0] + 'a'));
            sb.append((char)(second[0] + 'a'));
            if (--first[1] > 0) maxHeap.offer(first);
            if (--second[1] > 0) maxHeap.offer(second);
        }
        if (!maxHeap.isEmpty()) {
            int[] last = maxHeap.poll();
            if (last[1] > 1) return "";
            sb.append((char)(last[0] + 'a'));
        }
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem07_ReorganizeString sol = new Problem07_ReorganizeString();
        System.out.println(sol.reorganizeString("aab")); // "aba"
        System.out.println(sol.reorganizeString("aaab")); // ""
        System.out.println(sol.reorganizeString("vvvlo")); // "vlvov" or similar
    }
}
