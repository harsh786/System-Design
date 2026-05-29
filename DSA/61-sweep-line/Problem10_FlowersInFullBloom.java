import java.util.*;

public class Problem10_FlowersInFullBloom {
    public int[] fullBloomFlowers(int[][] flowers, int[] people) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int[] f : flowers) { map.merge(f[0], 1, Integer::sum); map.merge(f[1] + 1, -1, Integer::sum); }
        TreeMap<Integer, Integer> prefix = new TreeMap<>();
        int sum = 0;
        for (Map.Entry<Integer, Integer> e : map.entrySet()) { sum += e.getValue(); prefix.put(e.getKey(), sum); }
        int[] res = new int[people.length];
        for (int i = 0; i < people.length; i++) {
            Map.Entry<Integer, Integer> entry = prefix.floorEntry(people[i]);
            res[i] = entry == null ? 0 : entry.getValue();
        }
        return res;
    }

    public static void main(String[] args) {
        Problem10_FlowersInFullBloom sol = new Problem10_FlowersInFullBloom();
        System.out.println(Arrays.toString(sol.fullBloomFlowers(new int[][]{{1,6},{3,7},{9,12},{4,13}}, new int[]{2,3,7,11})));
    }
}
