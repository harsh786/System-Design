import java.util.*;

public class Problem42_SmallestRangeCoveringElementsFromKLists {
    // LC 632: Find smallest range that includes at least one number from each of k lists
    public static int[] smallestRange(List<List<Integer>> nums) {
        TreeMap<int[], Integer> map = new TreeMap<>((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        for (int i = 0; i < nums.size(); i++) map.put(new int[]{nums.get(i).get(0), i}, 0);
        int[] ans = {0, Integer.MAX_VALUE};
        while (map.size() == nums.size()) {
            int[] lo = map.firstKey(), hi = map.lastKey();
            if (hi[0] - lo[0] < ans[1] - ans[0]) { ans[0] = lo[0]; ans[1] = hi[0]; }
            int listIdx = lo[1], elemIdx = map.get(lo);
            map.remove(lo);
            if (elemIdx + 1 < nums.get(listIdx).size())
                map.put(new int[]{nums.get(listIdx).get(elemIdx + 1), listIdx}, elemIdx + 1);
        }
        return ans;
    }

    public static void main(String[] args) {
        List<List<Integer>> nums = Arrays.asList(
            Arrays.asList(4,10,15,24,26), Arrays.asList(0,9,12,20), Arrays.asList(5,18,22,30));
        System.out.println(Arrays.toString(smallestRange(nums))); // [20,24]
    }
}
