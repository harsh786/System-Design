import java.util.*;

public class Problem16_KthSmallestSum {
    /*
     * Find the Kth Smallest Sum of pairs from two sorted arrays
     * Time: O(k log k)
     */
    public int kthSmallestSum(int[] nums1, int[] nums2, int k) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> 
            (nums1[a[0]] + nums2[a[1]]) - (nums1[b[0]] + nums2[b[1]]));
        for (int i = 0; i < Math.min(nums1.length, k); i++) pq.offer(new int[]{i, 0});
        while (k-- > 1) {
            int[] cur = pq.poll();
            if (cur[1] + 1 < nums2.length) pq.offer(new int[]{cur[0], cur[1] + 1});
        }
        int[] res = pq.poll();
        return nums1[res[0]] + nums2[res[1]];
    }

    public static void main(String[] args) {
        Problem16_KthSmallestSum sol = new Problem16_KthSmallestSum();
        System.out.println(sol.kthSmallestSum(new int[]{1,7,11}, new int[]{2,4,6}, 3)); // 7
    }
}
