import java.util.*;

public class Problem11_KEmptySlots {
    // K Empty Slots: Given flowers blooming on days, find earliest day with k empty slots between two blooming flowers
    public static int kEmptySlots(int[] bulbs, int k) {
        TreeSet<Integer> blooming = new TreeSet<>();
        for (int day = 0; day < bulbs.length; day++) {
            int pos = bulbs[day];
            blooming.add(pos);
            Integer lo = blooming.lower(pos);
            Integer hi = blooming.higher(pos);
            if (lo != null && pos - lo - 1 == k) return day + 1;
            if (hi != null && hi - pos - 1 == k) return day + 1;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(kEmptySlots(new int[]{1,3,2}, 1)); // 2
        System.out.println(kEmptySlots(new int[]{1,2,3}, 1)); // 2
    }
}
