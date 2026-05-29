import java.util.*;

public class Problem21_NumberOfFlowersInFullBloom {
    // LC 2251: For each person's arrival time, count flowers in bloom
    public static int[] fullBloomFlowers(int[][] flowers, int[] people) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int[] f : flowers) {
            map.merge(f[0], 1, Integer::sum);
            map.merge(f[1] + 1, -1, Integer::sum);
        }
        // Build prefix sum
        TreeMap<Integer, Integer> prefix = new TreeMap<>();
        int sum = 0;
        for (var e : map.entrySet()) {
            sum += e.getValue();
            prefix.put(e.getKey(), sum);
        }
        int[] ans = new int[people.length];
        for (int i = 0; i < people.length; i++) {
            Integer key = prefix.floorKey(people[i]);
            ans[i] = key == null ? 0 : prefix.get(key);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(fullBloomFlowers(
            new int[][]{{1,6},{3,7},{9,12},{4,13}}, new int[]{2,3,7,11})));
        // [1,2,2,2]
    }
}
