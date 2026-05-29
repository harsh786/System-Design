import java.util.*;

public class Problem23_RevealCardsInIncreasingOrder {
    public static int[] deckRevealedIncreasing(int[] deck) {
        int n = deck.length;
        Arrays.sort(deck);
        Deque<Integer> dq = new ArrayDeque<>();
        for (int i = n - 1; i >= 0; i--) {
            if (!dq.isEmpty()) dq.offerFirst(dq.pollLast());
            dq.offerFirst(deck[i]);
        }
        int[] res = new int[n];
        for (int i = 0; i < n; i++) res[i] = dq.pollFirst();
        return res;
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(deckRevealedIncreasing(new int[]{17,13,11,2,3,5,7})));
    }
}
