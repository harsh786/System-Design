import java.util.*;

public class Problem02_KthSmallestElement {
    public int findKthSmallest(int[] nums, int k) {
        return quickselect(nums, 0, nums.length - 1, k - 1);
    }

    private int quickselect(int[] nums, int lo, int hi, int k) {
        if (lo == hi) return nums[lo];
        Random rand = new Random();
        int pi = lo + rand.nextInt(hi - lo + 1);
        pi = partition(nums, lo, hi, pi);
        if (k == pi) return nums[k];
        else if (k < pi) return quickselect(nums, lo, pi - 1, k);
        else return quickselect(nums, pi + 1, hi, k);
    }

    private int partition(int[] nums, int lo, int hi, int pi) {
        int pv = nums[pi];
        swap(nums, pi, hi);
        int s = lo;
        for (int i = lo; i < hi; i++) {
            if (nums[i] <= pv) { swap(nums, s, i); s++; }
        }
        swap(nums, s, hi);
        return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem02_KthSmallestElement sol = new Problem02_KthSmallestElement();
        System.out.println(sol.findKthSmallest(new int[]{7,10,4,3,20,15}, 3)); // 7
        System.out.println(sol.findKthSmallest(new int[]{12,3,5,7,19}, 2)); // 5
    }
}
