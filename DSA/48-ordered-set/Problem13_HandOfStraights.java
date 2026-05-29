import java.util.*;

public class Problem13_HandOfStraights {
    // LC 846: Divide hand into groups of consecutive cards of size groupSize
    public static boolean isNStraightHand(int[] hand, int groupSize) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int card : hand) map.merge(card, 1, Integer::sum);
        while (!map.isEmpty()) {
            int first = map.firstKey();
            for (int i = 0; i < groupSize; i++) {
                int card = first + i;
                if (!map.containsKey(card)) return false;
                map.merge(card, -1, Integer::sum);
                if (map.get(card) == 0) map.remove(card);
            }
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(isNStraightHand(new int[]{1,2,3,6,2,3,4,7,8}, 3)); // true
        System.out.println(isNStraightHand(new int[]{1,2,3,4,5}, 4)); // false
    }
}
