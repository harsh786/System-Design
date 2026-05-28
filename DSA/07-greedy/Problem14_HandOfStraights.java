/**
 * Problem 14: Hand of Straights (LeetCode 846)
 *
 * Greedy Choice: Always start a group from the smallest available card.
 *
 * Time: O(n log n), Space: O(n)
 *
 * Production Analogy: Grouping sequential log entries into complete transaction batches.
 */
import java.util.*;
public class Problem14_HandOfStraights {
    
    public static boolean isNStraightHand(int[] hand, int groupSize) {
        if (hand.length % groupSize != 0) return false;
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int h : hand) map.merge(h, 1, Integer::sum);
        while (!map.isEmpty()) {
            int first = map.firstKey();
            for (int i = first; i < first + groupSize; i++) {
                if (!map.containsKey(i)) return false;
                if (map.get(i) == 1) map.remove(i);
                else map.merge(i, -1, Integer::sum);
            }
        }
        return true;
    }
    
    public static void main(String[] args) {
        System.out.println(isNStraightHand(new int[]{1,2,3,6,2,3,4,7,8}, 3)); // true
        System.out.println(isNStraightHand(new int[]{1,2,3,4,5}, 4));          // false
    }
}
