/**
 * Problem: K Empty Slots with Window Min
 * Find window of size k where all values > endpoints using monotonic deque.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Finding gap of k unused resources between two active ones.
 */
import java.util.*;

public class Problem25_KEmptySlotsWindowMin {
    // Given days[] (1-indexed day each bulb turns on), find earliest day where
    // there are exactly k consecutive off-bulbs between two on-bulbs.
    public static int kEmptySlots(int[] bulbs, int k) {
        int n = bulbs.length;
        int[] days = new int[n]; // days[pos] = day it turns on
        for (int i = 0; i < n; i++) days[bulbs[i] - 1] = i + 1;
        // Find window of size k where all inner values > both endpoints
        int ans = Integer.MAX_VALUE;
        Deque<Integer> minDeque = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            while (!minDeque.isEmpty() && days[minDeque.peekLast()] >= days[i]) minDeque.pollLast();
            minDeque.offerLast(i);
            if (i >= k + 1) {
                if (minDeque.peekFirst() <= i - k - 1) minDeque.pollFirst();
                int left = i - k - 1, right = i;
                if (!minDeque.isEmpty() && days[minDeque.peekFirst()] > Math.max(days[left], days[right]))
                    ans = Math.min(ans, Math.max(days[left], days[right]));
            }
        }
        return ans == Integer.MAX_VALUE ? -1 : ans;
    }

    public static void main(String[] args) {
        System.out.println(kEmptySlots(new int[]{1, 3, 2}, 1)); // 2
        System.out.println(kEmptySlots(new int[]{1, 2, 3}, 1)); // -1 (no valid day)
    }
}
