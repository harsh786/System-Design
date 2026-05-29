import java.util.*;

public class Problem40_FindKClosestElements {
    // LC 658: Find k closest elements to x in sorted array
    public static List<Integer> findClosestElements(int[] arr, int k, int x) {
        TreeMap<Integer, List<Integer>> map = new TreeMap<>();
        for (int a : arr) {
            int diff = Math.abs(a - x);
            map.computeIfAbsent(diff, d -> new ArrayList<>()).add(a);
        }
        List<Integer> result = new ArrayList<>();
        for (var e : map.entrySet()) {
            for (int v : e.getValue()) {
                if (result.size() < k) result.add(v);
                else break;
            }
            if (result.size() >= k) break;
        }
        Collections.sort(result);
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findClosestElements(new int[]{1,2,3,4,5}, 4, 3)); // [1,2,3,4]
    }
}
