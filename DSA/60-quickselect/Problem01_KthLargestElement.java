import java.util.*;

public class Problem01_KthLargestElement {
    /*
     * Kth Largest Element in an Array
     * Given an integer array nums and an integer k, return the kth largest element.
     * Use Quickselect for O(n) average time.
     *
     * Time: O(n) average, O(n^2) worst case
     * Space: O(1)
     */
    public int findKthLargest(int[] nums, int k) {
        int target = nums.length - k; // convert to kth smallest (0-indexed)
        return quickselect(nums, 0, nums.length - 1, target);
    }

    private int quickselect(int[] nums, int left, int right, int k) {
        if (left == right) return nums[left];
        Random rand = new Random();
        int pivotIndex = left + rand.nextInt(right - left + 1);
        pivotIndex = partition(nums, left, right, pivotIndex);
        if (k == pivotIndex) return nums[k];
        else if (k < pivotIndex) return quickselect(nums, left, pivotIndex - 1, k);
        else return quickselect(nums, pivotIndex + 1, right, k);
    }

    private int partition(int[] nums, int left, int right, int pivotIndex) {
        int pivotValue = nums[pivotIndex];
        swap(nums, pivotIndex, right);
        int storeIndex = left;
        for (int i = left; i < right; i++) {
            if (nums[i] < pivotValue) {
                swap(nums, storeIndex, i);
                storeIndex++;
            }
        }
        swap(nums, storeIndex, right);
        return storeIndex;
    }

    private void swap(int[] nums, int i, int j) {
        int tmp = nums[i]; nums[i] = nums[j]; nums[j] = tmp;
    }

    public static void main(String[] args) {
        Problem01_KthLargestElement sol = new Problem01_KthLargestElement();
        System.out.println(sol.findKthLargest(new int[]{3,2,1,5,6,4}, 2)); // 5
        System.out.println(sol.findKthLargest(new int[]{3,2,3,1,2,4,5,5,6}, 4)); // 4
    }
}
