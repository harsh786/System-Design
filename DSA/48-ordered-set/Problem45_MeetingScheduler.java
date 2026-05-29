import java.util.*;

public class Problem45_MeetingScheduler {
    // LC 1229: Find earliest time slot that works for both persons with given duration
    public static List<Integer> minAvailableDuration(int[][] slots1, int[][] slots2, int duration) {
        TreeMap<Integer, Integer> map1 = new TreeMap<>();
        for (int[] s : slots1) map1.put(s[0], s[1]);
        Arrays.sort(slots2, (a, b) -> a[0] - b[0]);
        for (int[] s : slots2) {
            Integer key = map1.floorKey(s[1] - 1);
            while (key != null && map1.get(key) > s[0]) {
                int start = Math.max(key, s[0]);
                int end = Math.min(map1.get(key), s[1]);
                if (end - start >= duration) return Arrays.asList(start, start + duration);
                key = map1.lowerKey(key);
            }
        }
        return new ArrayList<>();
    }

    public static void main(String[] args) {
        System.out.println(minAvailableDuration(
            new int[][]{{10,50},{60,120},{140,210}},
            new int[][]{{0,15},{60,70}}, 8)); // [60,68]
    }
}
