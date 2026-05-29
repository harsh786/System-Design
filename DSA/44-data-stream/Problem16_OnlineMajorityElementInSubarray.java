import java.util.*;

public class Problem16_OnlineMajorityElementInSubarray {
    // 1157. Online Majority Element In Subarray. Randomized approach.
    
    int[] arr;
    Map<Integer, List<Integer>> positions = new HashMap<>();
    Random rand = new Random();
    
    public void init(int[] arr) {
        this.arr = arr;
        for (int i = 0; i < arr.length; i++)
            positions.computeIfAbsent(arr[i], k -> new ArrayList<>()).add(i);
    }
    
    public int query(int left, int right, int threshold) {
        // Random sampling: pick random elements and check if majority
        for (int trial = 0; trial < 20; trial++) {
            int idx = left + rand.nextInt(right - left + 1);
            int candidate = arr[idx];
            List<Integer> pos = positions.get(candidate);
            int lo = Collections.binarySearch(pos, left);
            if (lo < 0) lo = -lo - 1;
            int hi = Collections.binarySearch(pos, right);
            if (hi < 0) hi = -hi - 2; else hi = hi;
            if (hi - lo + 1 >= threshold) return candidate;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        Problem16_OnlineMajorityElementInSubarray sol = new Problem16_OnlineMajorityElementInSubarray();
        sol.init(new int[]{1,1,2,2,1,1});
        System.out.println(sol.query(0, 5, 4)); // 1
        System.out.println(sol.query(2, 3, 2)); // -1
    }
}
