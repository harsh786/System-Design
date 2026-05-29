/**
 * Problem: Reveal Cards In Increasing Order (LeetCode 950)
 * Approach: Simulate reverse process using deque
 * Complexity: O(n log n) time, O(n) space
 * Production Analogy: Reverse-engineering output order for pipeline scheduling
 */
import java.util.*;
public class Problem29_RevealCardsIncreasingOrder {
    public int[] deckRevealedIncreasing(int[] deck) {
        Arrays.sort(deck);
        Deque<Integer> dq = new ArrayDeque<>();
        for (int i = deck.length-1; i >= 0; i--) {
            if (!dq.isEmpty()) dq.offerFirst(dq.pollLast());
            dq.offerFirst(deck[i]);
        }
        int[] res = new int[deck.length];
        for (int i = 0; i < res.length; i++) res[i] = dq.pollFirst();
        return res;
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem29_RevealCardsIncreasingOrder()
            .deckRevealedIncreasing(new int[]{17,13,11,2,3,5,7})));
    }
}
